"""FastAPI server for Interview Copilot."""

import os
import asyncio
import json
import wave
import io
import time
from contextlib import suppress
from datetime import datetime
from difflib import SequenceMatcher
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# 显式加载项目根目录的 .env（无论从哪个目录启动服务端都能找到）
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
load_dotenv(dotenv_path=_env_path)
print(f"[ENV] 加载 .env: {_env_path}")
print(f"[ENV] DOUBAO_APP_ID={os.getenv('DOUBAO_APP_ID', '(未设置)')}")


try:
    from server.asr import get_asr_processor
    from server.intent import IntentReadinessDetector
    from server.llm import llm_processor
except ModuleNotFoundError:
    # Fallback for running from server/ directory directly.
    from asr import get_asr_processor
    from intent import IntentReadinessDetector
    from llm import llm_processor

app = FastAPI(title="Interview Copilot")

# CORS for Chrome extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global context (in-memory, single user)
JD_TEXT: str = ""
RESUME_TEXT: str = ""
LLM_OUTLINE_TIMEOUT_SECONDS = 8
LLM_ANSWER_TIMEOUT_SECONDS = 18
LLM_ANALYSIS_TIMEOUT_SECONDS = 45
ANSWER_FALLBACK_TEXT = "抱歉，我刚才没来得及生成完整回答。请让我复述一遍这个问题，我会马上给你一个结构化回答。"
ANALYSIS_FALLBACK_TEXT = "本次复盘生成超时或失败，请稍后重试。"


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


class ContextInput(BaseModel):
    jd: str
    resume: str = ""
    extra_info: str = ""


@app.post("/set_context")
async def set_context(context: ContextInput):
    """Set JD and Resume context (including supplemental user info)."""
    global JD_TEXT, RESUME_TEXT
    JD_TEXT = context.jd
    # 将简历与补充信息合并，作为完整的用户背景上下文
    parts = []
    if context.resume:
        parts.append(f"【个人简历】\n{context.resume}")
    if context.extra_info:
        parts.append(f"【其他补充信息】\n{context.extra_info}")
    RESUME_TEXT = "\n\n".join(parts)
    return {"status": "ok", "message": "Context saved"}


@app.post("/parse_resume")
async def parse_resume(file: UploadFile = File(...)):
    """Parse resume from PDF, Docx, or Image."""
    filename = file.filename.lower()
    content = await file.read()
    text = ""

    try:
        if filename.endswith(".pdf"):
            try:
                import fitz  # PyMuPDF
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Missing dependency: PyMuPDF. Run `pip install -r requirements.txt` in server/.",
                )
            doc = fitz.open(stream=content, filetype="pdf")
            for page in doc:
                text += page.get_text()
        elif filename.endswith((".docx", ".doc")):
            try:
                from docx import Document
            except ImportError:
                raise HTTPException(
                    status_code=500,
                    detail="Missing dependency: python-docx. Run `pip install -r requirements.txt` in server/.",
                )
            doc = Document(io.BytesIO(content))
            text = "\n".join([para.text for para in doc.paragraphs])
        elif filename.endswith((".png", ".jpg", ".jpeg")):
            # Use LLM Vision for images
            # For now, let's assume we have a method in llm_processor or use a simple OCR prompt
            # Since OpenAIProcessor doesn't have it yet, we'll placeholder it with a note
            # but ideally we'd call a vision model.
            text = "[图片简历解析需调用 Vision 模型，暂未实现具体 OCR 逻辑]"
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        return {"status": "ok", "text": text.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.websocket("/ws/audio")
async def audio_websocket(websocket: WebSocket):
    """WebSocket endpoint for audio streaming."""
    await websocket.accept()

    # Session Memory Setup
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    records_dir = os.path.join(os.path.dirname(__file__), "records")
    os.makedirs(records_dir, exist_ok=True)

    audio_file_path = os.path.join(records_dir, f"session_{session_id}.wav")
    transcript_file_path = os.path.join(records_dir, f"session_{session_id}.json")

    # Initialize wave writer
    wave_file = wave.open(audio_file_path, "wb")
    wave_file.setnchannels(1)
    wave_file.setsampwidth(2)  # 16-bit
    wave_file.setframerate(16000)

    # In-memory transcript log
    session_transcript = []

    # State tracking per connection
    background_tasks = set()
    answer_tasks = set()
    answer_generation_lock = asyncio.Lock()
    intent_detector = IntentReadinessDetector()
    outline_task = None
    next_answer_seq = 1
    last_final_text = ""
    last_final_ts = 0.0

    # We will need the event loop for the async callback
    loop = asyncio.get_running_loop()

    async def _call_with_timeout(coro, timeout_seconds: int, fallback_text: str) -> str:
        try:
            result = await asyncio.wait_for(coro, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            print(f"[LLM] 调用超时（>{timeout_seconds}s）")
            return fallback_text
        except Exception as e:
            print(f"[LLM] 调用失败: {e}")
            return fallback_text
        result = (result or "").strip()
        return result or fallback_text

    def _sorted_transcript():
        return sorted(session_transcript, key=lambda turn: turn.get("seq", 0))

    def _build_history_text() -> str:
        history_text = ""
        for idx, turn in enumerate(_sorted_transcript()):
            history_text += (
                f"Q{idx+1}: {turn['面试官的问题']}\nA{idx+1}: {turn['AI参考回答']}\n\n"
            )
        return history_text.strip()

    def _schedule_answer(question_text: str, source: str):
        nonlocal next_answer_seq
        answer_seq = next_answer_seq
        next_answer_seq += 1

        async def _do_answer(seq: int, question_snapshot: str, source_snapshot: str):
            nonlocal session_transcript
            try:
                async with answer_generation_lock:
                    answer = await _call_with_timeout(
                        llm_processor.generate_answer(
                            jd=JD_TEXT, resume=RESUME_TEXT, question=question_snapshot
                        ),
                        timeout_seconds=LLM_ANSWER_TIMEOUT_SECONDS,
                        fallback_text=ANSWER_FALLBACK_TEXT,
                    )
                print(f"[LLM] Answer(seq={seq}): {answer}")
                session_transcript.append(
                    {
                        "seq": seq,
                        "source": source_snapshot,
                        "面试官的问题": question_snapshot,
                        "AI参考回答": answer,
                    }
                )
                try:
                    await websocket.send_json(
                        {
                            "type": "answer",
                            "question": question_snapshot,
                            "answer": answer,
                            "seq": seq,
                        }
                    )
                except Exception as e:
                    print(f"[WS] Error sending answer: {e}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"[LLM] 生成回答任务异常: {e}")

        task = asyncio.create_task(_do_answer(answer_seq, question_text, source))
        answer_tasks.add(task)
        background_tasks.add(task)
        task.add_done_callback(answer_tasks.discard)
        task.add_done_callback(background_tasks.discard)

    async def on_text_update(text: str, is_sentence_end: bool):
        """Callback fired by the ASR processor when new text is recognized."""
        nonlocal outline_task, last_final_text, last_final_ts
        # print(f"[ASR] Incremental: {text} | End: {is_sentence_end}") # Too noisy

        if not text:
            return

        # 0. Send incremental text to client for real-time feedback
        try:
            await websocket.send_json({"type": "incremental", "text": text})
        except Exception:
            pass

        # 1. Early draft outline (intent-ready partial only)
        if not is_sentence_end and intent_detector.should_trigger_outline(text):
            print("[LLM] Intent ready. Generating draft outline...")

            if outline_task and not outline_task.done():
                outline_task.cancel()

            outline_seq = next_answer_seq

            async def _do_outline(question_snapshot: str, seq: int):
                try:
                    outline = await _call_with_timeout(
                        llm_processor.generate_outline(
                            jd=JD_TEXT, resume=RESUME_TEXT, question=question_snapshot
                        ),
                        timeout_seconds=LLM_OUTLINE_TIMEOUT_SECONDS,
                        fallback_text="",
                    )
                except asyncio.CancelledError:
                    return
                print(f"[LLM] Outline(seq={seq}): {outline}")
                if not outline:
                    return
                draft_text = f"【要点草稿】\n{outline}"
                try:
                    await websocket.send_json(
                        {
                            "type": "outline",
                            "question": question_snapshot,
                            "answer": draft_text,
                            "seq": seq,
                        }
                    )
                except Exception as e:
                    print(f"[WS] Error sending outline: {e}")

            outline_task = asyncio.create_task(_do_outline(text, outline_seq))
            background_tasks.add(outline_task)
            outline_task.add_done_callback(background_tasks.discard)

        # 2. End of Sentence -> Full Answer
        if is_sentence_end:
            normalized = _normalize_text(text)
            now_ts = time.monotonic()
            # ASR 可能重复发送同一句 final，做去重避免重复回答
            if (
                normalized
                and _similarity(normalized, last_final_text) >= 0.97
                and (now_ts - last_final_ts) <= 8
            ):
                print(f"[LLM] 跳过重复 final: {text}")
                return

            last_final_text = normalized
            last_final_ts = now_ts
            print("[LLM] Sentence complete. Generating full answer...")
            intent_detector.reset()
            if outline_task and not outline_task.done():
                outline_task.cancel()
            _schedule_answer(text, source="asr")

    # Initialize and start ASR stream (per-connection instance; do not share globally)
    asr_processor = get_asr_processor()
    asr_processor.set_callback(on_text_update, loop)
    try:
        asr_processor.start()
    except Exception as e:
        print(f"[ASR] Failed to start ASR: {e}")
        await websocket.close()
        wave_file.close()
        return

    try:
        _recv_count = 0
        while True:
            # Receive audio chunk (binary) or command (text)
            message = await websocket.receive()
            if "bytes" in message:
                data = message["bytes"]
                _recv_count += 1
                if _recv_count % 100 == 1:
                    print(
                        f"[WS] Received binary frame #{_recv_count}  size={len(data)}B"
                    )
                # Save to disk
                wave_file.writeframes(data)
                # Stream to ASR
                asr_processor.add_audio(data)
            elif "text" in message:
                text_data = message["text"]
                print(f"[WS] Received text frame: {text_data[:80]}")

                try:
                    cmd_json = json.loads(text_data)
                    if cmd_json.get("command") == "end_session":
                        print(
                            f"[Memory] Session ended by user. Generating analysis for: {session_id}"
                        )
                        # Stop ASR first so no more late transcripts are appended.
                        asr_processor.stop()

                        if outline_task and not outline_task.done():
                            outline_task.cancel()

                        # 等待已触发但未完成的回答任务，确保复盘包含最新回答
                        pending_answers = [task for task in answer_tasks if not task.done()]
                        if pending_answers:
                            await asyncio.gather(
                                *pending_answers, return_exceptions=True
                            )

                        # Format history for LLM
                        history_text = _build_history_text()

                        # Generate Analysis
                        analysis = await _call_with_timeout(
                            llm_processor.generate_analysis(
                                jd=JD_TEXT, resume=RESUME_TEXT, history=history_text
                            ),
                            timeout_seconds=LLM_ANALYSIS_TIMEOUT_SECONDS,
                            fallback_text=ANALYSIS_FALLBACK_TEXT,
                        )

                        # Save Transcript + Analysis
                        with open(transcript_file_path, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "jd": JD_TEXT,
                                    "resume": RESUME_TEXT,
                                    "history": _sorted_transcript(),
                                    "analysis": analysis,
                                },
                                f,
                                ensure_ascii=False,
                                indent=2,
                            )

                        # Send analysis back to client and close this session loop.
                        await websocket.send_json(
                            {"type": "analysis", "answer": analysis}
                        )
                        break
                    elif cmd_json.get("command") == "manual_question":
                        # 用户通过悬浮窗输入框手动提问
                        manual_text = cmd_json.get("text", "").strip()
                        if manual_text:
                            print(f"[Manual] User sent: {manual_text}")
                            intent_detector.reset()
                            if outline_task and not outline_task.done():
                                outline_task.cancel()
                            _schedule_answer(manual_text, source="manual")

                except Exception as e:
                    print(f"[WS] Error processing text command: {e}")

    except WebSocketDisconnect:
        print("[WS] Client disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        asr_processor.stop()
        for task in background_tasks:
            task.cancel()
        with suppress(Exception):
            await asyncio.gather(*background_tasks, return_exceptions=True)
        wave_file.close()

        # Save partial transcript on sudden disconnect
        if not os.path.exists(transcript_file_path) and session_transcript:
            with open(transcript_file_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "jd": JD_TEXT,
                        "resume": RESUME_TEXT,
                        "history": _sorted_transcript(),
                        "analysis": "未正常结束，未能生成点评。",
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
