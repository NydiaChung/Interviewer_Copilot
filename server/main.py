"""FastAPI server for Interview Copilot."""

import os
import asyncio
import json
import wave
import io
from contextlib import suppress
from datetime import datetime
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
    from server.llm import llm_processor
except ModuleNotFoundError:
    # Fallback for running from server/ directory directly.
    from asr import get_asr_processor
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
    has_generated_outline = False
    current_sentence = ""
    OUTLINE_CHAR_THRESHOLD = 8  # characters required to trigger early intent outline
    background_tasks = set()

    # We will need the event loop for the async callback
    loop = asyncio.get_running_loop()

    async def on_text_update(text: str, is_sentence_end: bool):
        """Callback fired by the ASR processor when new text is recognized."""
        nonlocal has_generated_outline, current_sentence, session_transcript

        current_sentence = text
        # print(f"[ASR] Incremental: {text} | End: {is_sentence_end}") # Too noisy

        if not text:
            return

        # 0. Send incremental text to client for real-time feedback
        try:
            await websocket.send_json({"type": "incremental", "text": text})
        except:
            pass

        # 1. Early Intent Outline Detection
        # If we haven't generated an outline yet, and the text is long enough
        if not has_generated_outline and len(text) >= OUTLINE_CHAR_THRESHOLD:
            has_generated_outline = True
            print("[LLM] Generating early intent outline...")

            # Fire and forget the outline generation, so we don't block
            async def _do_outline():
                outline = await llm_processor.generate_outline(
                    jd=JD_TEXT, resume=RESUME_TEXT, question=text
                )
                print(f"[LLM] Outline: {outline}")
                try:
                    await websocket.send_json(
                        {"type": "outline", "question": text, "answer": outline}
                    )
                except Exception as e:
                    print(f"[WS] Error sending outline: {e}")

            task = asyncio.create_task(_do_outline())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

        # 2. End of Sentence -> Full Answer
        if is_sentence_end:
            print("[LLM] Sentence complete. Generating full answer...")
            # We reset outline flag for the next sentence
            has_generated_outline = False

            async def _do_answer():
                nonlocal session_transcript
                answer = await llm_processor.generate_answer(
                    jd=JD_TEXT, resume=RESUME_TEXT, question=text
                )
                print(f"[LLM] Answer: {answer}")

                # Append to transcript memory
                session_transcript.append({"面试官的问题": text, "AI参考回答": answer})

                try:
                    await websocket.send_json(
                        {"type": "answer", "question": text, "answer": answer}
                    )
                except Exception as e:
                    print(f"[WS] Error sending answer: {e}")

            task = asyncio.create_task(_do_answer())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)

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

                        # Format history for LLM
                        history_text = ""
                        for idx, turn in enumerate(session_transcript):
                            history_text += f"Q{idx+1}: {turn['面试官的问题']}\nA{idx+1}: {turn['AI参考回答']}\n\n"

                        # Generate Analysis
                        analysis = await llm_processor.generate_analysis(
                            jd=JD_TEXT, resume=RESUME_TEXT, history=history_text.strip()
                        )

                        # Save Transcript + Analysis
                        with open(transcript_file_path, "w", encoding="utf-8") as f:
                            json.dump(
                                {
                                    "jd": JD_TEXT,
                                    "resume": RESUME_TEXT,
                                    "history": session_transcript,
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

                            # 记录到 transcript
                            async def _do_manual_answer():
                                nonlocal session_transcript
                                answer = await llm_processor.generate_answer(
                                    jd=JD_TEXT, resume=RESUME_TEXT, question=manual_text
                                )
                                session_transcript.append(
                                    {"面试官的问题": manual_text, "AI参考回答": answer}
                                )
                                try:
                                    await websocket.send_json(
                                        {
                                            "type": "answer",
                                            "question": manual_text,
                                            "answer": answer,
                                        }
                                    )
                                except Exception as e:
                                    print(f"[WS] Error sending manual answer: {e}")

                            task = asyncio.create_task(_do_manual_answer())
                            background_tasks.add(task)
                            task.add_done_callback(background_tasks.discard)

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
                        "history": session_transcript,
                        "analysis": "未正常结束，未能生成点评。",
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
