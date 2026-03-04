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
    from server.voiceprint import VoiceprintTracker
except ModuleNotFoundError:
    # Fallback for running from server/ directory directly.
    from asr import get_asr_processor
    from intent import IntentReadinessDetector
    from llm import llm_processor
    from voiceprint import VoiceprintTracker

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
QUESTION_CLOSE_SILENCE_SECONDS = 0.9
QUESTION_FORCE_CLOSE_SECONDS = 2.6
NEW_QUESTION_SIMILARITY_THRESHOLD = 0.45
VOICEPRINT_SWITCH_MIN_GAP_SECONDS = 0.35
VOICEPRINT_SWITCH_SIMILARITY_THRESHOLD = 0.72
ANSWER_STREAM_INTERVAL_SECONDS = 0.04


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _is_question_like(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    hints = (
        "?",
        "？",
        "吗",
        "呢",
        "么",
        "如何",
        "怎么",
        "为什么",
        "是否",
        "请你",
        "能否",
    )
    return any(h in t for h in hints)


def _chunk_answer_text(text: str):
    """Chunk answer text for incremental UI updates."""
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    buf = ""
    split_chars = set("，。！？；,.!?\n")
    for ch in text:
        buf += ch
        if (ch in split_chars and len(buf) >= 6) or len(buf) >= 20:
            chunks.append(buf)
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


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
    close_check_task = None
    current_turn = None
    next_turn_id = 1
    next_answer_seq = 1
    last_answer_trigger_text = ""
    last_answer_trigger_ts = 0.0
    voiceprint_tracker = VoiceprintTracker()
    last_dominant_speaker = None
    last_speaker_change_ts = 0.0

    # We will need the event loop for the async callback
    loop = asyncio.get_running_loop()

    def _create_turn(
        text: str, normalized: str, now_ts: float, speaker_id: int | None = None
    ):
        nonlocal next_turn_id
        turn = {
            "id": next_turn_id,
            "text": text,
            "norm": normalized,
            "created_ts": now_ts,
            "last_ts": now_ts,
            "got_final": False,
            "draft_sent": False,
            "closed": False,
            "speaker_id": speaker_id,
        }
        next_turn_id += 1
        return turn

    def _is_speaker_switched(turn: dict, incoming_speaker: int | None) -> bool:
        turn_speaker = turn.get("speaker_id")
        return (
            incoming_speaker is not None
            and turn_speaker is not None
            and incoming_speaker != turn_speaker
        )

    def _current_dominant_speaker(now_ts: float) -> int | None:
        speaker_id = voiceprint_tracker.dominant_speaker(now_ts)
        if speaker_id is not None:
            return speaker_id
        return last_dominant_speaker

    def _should_start_new_turn(
        turn: dict, incoming_norm: str, now_ts: float, incoming_speaker: int | None
    ) -> bool:
        if not turn or turn.get("closed"):
            return False
        speaker_switched = _is_speaker_switched(turn, incoming_speaker)
        if len(turn.get("norm", "")) < 10 or len(incoming_norm) < 6:
            if speaker_switched and turn.get("got_final") and len(incoming_norm) >= 4:
                return True
            return False
        sim = _similarity(incoming_norm, turn.get("norm", ""))
        if sim >= NEW_QUESTION_SIMILARITY_THRESHOLD and not speaker_switched:
            return False
        if (
            speaker_switched
            and sim <= VOICEPRINT_SWITCH_SIMILARITY_THRESHOLD
            and (now_ts - turn.get("last_ts", now_ts))
            >= VOICEPRINT_SWITCH_MIN_GAP_SECONDS
        ):
            return True
        if turn.get("got_final"):
            return True
        if (
            _is_question_like(turn.get("text", ""))
            and (now_ts - turn.get("last_ts", now_ts)) >= 0.55
        ):
            return True
        return False

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

    async def _stream_answer_to_client(
        seq: int, question_snapshot: str, answer_text: str, question_id
    ):
        chunks = _chunk_answer_text(answer_text)
        if not chunks:
            chunks = [answer_text]
        if len(chunks) == 1:
            await websocket.send_json(
                {
                    "type": "answer",
                    "question": question_snapshot,
                    "answer": answer_text,
                    "seq": seq,
                    "question_id": question_id,
                    "streaming": False,
                }
            )
            return

        partial = ""
        for chunk in chunks:
            partial += chunk
            await websocket.send_json(
                {
                    "type": "answer",
                    "question": question_snapshot,
                    "answer": partial,
                    "seq": seq,
                    "question_id": question_id,
                    "streaming": True,
                }
            )
            await asyncio.sleep(ANSWER_STREAM_INTERVAL_SECONDS)
        await websocket.send_json(
            {
                "type": "answer",
                "question": question_snapshot,
                "answer": answer_text,
                "seq": seq,
                "question_id": question_id,
                "streaming": False,
            }
        )

    def _schedule_answer(question_text: str, source: str, question_id=None):
        nonlocal next_answer_seq
        answer_seq = next_answer_seq
        next_answer_seq += 1

        async def _do_answer(
            seq: int, question_snapshot: str, source_snapshot: str, qid
        ):
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
                        "question_id": qid,
                        "面试官的问题": question_snapshot,
                        "AI参考回答": answer,
                    }
                )
                await _stream_answer_to_client(seq, question_snapshot, answer, qid)
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"[LLM] 生成回答任务异常: {e}")

        task = asyncio.create_task(
            _do_answer(answer_seq, question_text, source, question_id)
        )
        answer_tasks.add(task)
        background_tasks.add(task)
        task.add_done_callback(answer_tasks.discard)
        task.add_done_callback(background_tasks.discard)

    async def _maybe_close_turn(turn_id: int, reason: str, force: bool = False) -> bool:
        nonlocal current_turn, outline_task, last_answer_trigger_text, last_answer_trigger_ts
        turn = current_turn
        if not turn or turn.get("id") != turn_id or turn.get("closed"):
            return False

        now_ts = time.monotonic()
        silence = now_ts - turn.get("last_ts", now_ts)
        dominant_speaker = _current_dominant_speaker(now_ts)
        speaker_switched = _is_speaker_switched(turn, dominant_speaker)
        speaker_switched_recently = (
            speaker_switched and (now_ts - last_speaker_change_ts) <= 1.6
        )
        should_close = (
            force
            or (
                silence >= QUESTION_CLOSE_SILENCE_SECONDS
                and (turn.get("got_final") or _is_question_like(turn.get("text", "")))
            )
            or (
                silence >= VOICEPRINT_SWITCH_MIN_GAP_SECONDS
                and speaker_switched_recently
                and len(turn.get("norm", "")) >= 8
            )
            or silence >= QUESTION_FORCE_CLOSE_SECONDS
        )
        if not should_close:
            return False

        turn["closed"] = True
        turn["close_reason"] = reason
        intent_detector.reset()
        if outline_task and not outline_task.done():
            outline_task.cancel()

        normalized = turn.get("norm", "")
        if (
            normalized
            and _similarity(normalized, last_answer_trigger_text) >= 0.97
            and (now_ts - last_answer_trigger_ts) <= 8
        ):
            print(f"[LLM] 跳过重复问题触发: {turn.get('text', '')}")
            current_turn = None
            return True

        last_answer_trigger_text = normalized
        last_answer_trigger_ts = now_ts
        _schedule_answer(turn.get("text", ""), source="asr", question_id=turn.get("id"))
        current_turn = None
        return True

    def _arm_close_check(turn_id: int):
        nonlocal close_check_task
        if close_check_task and not close_check_task.done():
            close_check_task.cancel()

        async def _wait_and_check():
            try:
                await asyncio.sleep(QUESTION_CLOSE_SILENCE_SECONDS)
                closed = await _maybe_close_turn(turn_id, reason="silence")
                if (
                    not closed
                    and current_turn
                    and current_turn.get("id") == turn_id
                    and not current_turn.get("closed")
                ):
                    _arm_close_check(turn_id)
            except asyncio.CancelledError:
                return

        close_check_task = asyncio.create_task(_wait_and_check())
        background_tasks.add(close_check_task)
        close_check_task.add_done_callback(background_tasks.discard)

    async def on_text_update(text: str, is_sentence_end: bool):
        """Callback fired by the ASR processor when new text is recognized."""
        nonlocal current_turn, outline_task
        if not text:
            return

        now_ts = time.monotonic()
        normalized = _normalize_text(text)
        incoming_speaker = _current_dominant_speaker(now_ts)

        if current_turn and _should_start_new_turn(
            current_turn, normalized, now_ts, incoming_speaker
        ):
            await _maybe_close_turn(
                current_turn.get("id"), reason="next_question_start", force=True
            )

        if not current_turn:
            current_turn = _create_turn(text, normalized, now_ts, incoming_speaker)
        else:
            # 只有当识别到的内容发生实质变化时，才更新计时器
            if normalized != current_turn.get("norm"):
                current_turn["last_ts"] = now_ts

            current_turn["text"] = text
            current_turn["norm"] = normalized
            if current_turn.get("speaker_id") is None and incoming_speaker is not None:
                current_turn["speaker_id"] = incoming_speaker

        if is_sentence_end:
            current_turn["got_final"] = True

        # Send incremental text with question_id for debug/traceability.
        try:
            await websocket.send_json(
                {
                    "type": "incremental",
                    "text": text,
                    "question_id": current_turn.get("id"),
                    "speaker_id": incoming_speaker,
                }
            )
        except Exception:
            pass

        # Early draft outline: one shot per question.
        if (
            not current_turn.get("draft_sent")
            and not is_sentence_end
            and intent_detector.should_trigger_outline(text)
        ):
            print("[LLM] Intent ready. Generating draft outline...")
            current_turn["draft_sent"] = True
            turn_id = current_turn.get("id")
            outline_seq = next_answer_seq

            if outline_task and not outline_task.done():
                outline_task.cancel()

            async def _do_outline(question_snapshot: str, seq: int, qid: int):
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
                if not outline:
                    return
                if (
                    not current_turn
                    or current_turn.get("id") != qid
                    or current_turn.get("closed")
                ):
                    return
                draft_text = f"【要点草稿】\n{outline}"
                try:
                    await websocket.send_json(
                        {
                            "type": "outline",
                            "question": question_snapshot,
                            "answer": draft_text,
                            "seq": seq,
                            "question_id": qid,
                        }
                    )
                except Exception as e:
                    print(f"[WS] Error sending outline: {e}")

            outline_task = asyncio.create_task(_do_outline(text, outline_seq, turn_id))
            background_tasks.add(outline_task)
            outline_task.add_done_callback(background_tasks.discard)

        _arm_close_check(current_turn.get("id"))

        if is_sentence_end:
            await _maybe_close_turn(current_turn.get("id"), reason="asr_final")

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
                now_ts = time.monotonic()
                _recv_count += 1
                if _recv_count % 100 == 1:
                    print(
                        f"[WS] Received binary frame #{_recv_count}  size={len(data)}B"
                    )
                # Save to disk
                wave_file.writeframes(data)
                # Stream to ASR
                asr_processor.add_audio(data)
                sid = voiceprint_tracker.update_audio(data, ts=now_ts)
                if sid is not None:
                    dominant = voiceprint_tracker.dominant_speaker(now_ts)
                    if dominant is not None and dominant != last_dominant_speaker:
                        last_dominant_speaker = dominant
                        last_speaker_change_ts = now_ts
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

                        if close_check_task and not close_check_task.done():
                            close_check_task.cancel()
                        if outline_task and not outline_task.done():
                            outline_task.cancel()
                        if current_turn and not current_turn.get("closed"):
                            await _maybe_close_turn(
                                current_turn.get("id"),
                                reason="session_end",
                                force=True,
                            )

                        # 等待已触发但未完成的回答任务，确保复盘包含最新回答
                        pending_answers = [
                            task for task in answer_tasks if not task.done()
                        ]
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
                            if close_check_task and not close_check_task.done():
                                close_check_task.cancel()
                            intent_detector.reset()
                            if outline_task and not outline_task.done():
                                outline_task.cancel()
                            if current_turn and not current_turn.get("closed"):
                                await _maybe_close_turn(
                                    current_turn.get("id"),
                                    reason="manual_interrupt",
                                    force=True,
                                )
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
