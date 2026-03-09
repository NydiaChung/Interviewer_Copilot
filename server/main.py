"""FastAPI server for Interview Copilot."""

import os
import asyncio
import json
import wave
import io
import time
import base64
import audioop
import uuid
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
    from server.asr import DoubaoProvider, TingwuProvider, get_asr_processor
    from server.intent import IntentReadinessDetector, is_question_like
    from server.llm import llm_processor
    from server.voiceprint import VoiceprintTracker
except ModuleNotFoundError:
    # Fallback for running from server/ directory directly.
    from asr import DoubaoProvider, TingwuProvider, get_asr_processor
    from intent import IntentReadinessDetector, is_question_like
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
#
ANSWER_STREAM_INTERVAL_SECONDS = 0.04
# 声纹换人后，满足该沉默时间即强制关闭问题并触发回答
VOICEPRINT_CLOSE_SILENCE_SECONDS = 0.35
# 有效语音能量阈值（过低会把底噪当成“仍在说话”）
TURN_ACTIVE_AUDIO_RMS = 220
# 关闭监视器的轮询间隔（Fix 3：单一协程替代递归Task）
CLOSE_WATCHER_POLL_SECONDS = 0.25
# 声纹：新说话人连续出现多少帧才算「确认切换」，防止噪声/单帧抖动误判
SPEAKER_CONFIRM_FRAMES = 4
# 声纹确认帧间最大时间间隔（超过则重新计数）
SPEAKER_CONFIRM_MAX_GAP_SECONDS = 0.5
# tracing 开关与采样
TRACE_ENABLED = os.getenv("TRACE_ENABLED", "1").lower() not in ("0", "false", "off")
TRACE_AUDIO_SAMPLE_EVERY = int(os.getenv("TRACE_AUDIO_SAMPLE_EVERY", "80"))
ASR_STALL_ACTIVE_FRAMES = int(os.getenv("ASR_STALL_ACTIVE_FRAMES", "35"))
ASR_RESTART_COOLDOWN_SECONDS = float(os.getenv("ASR_RESTART_COOLDOWN_SECONDS", "8.0"))
CANDIDATE_ASR_RETRY_SECONDS = float(os.getenv("CANDIDATE_ASR_RETRY_SECONDS", "6.0"))
# 音源角色判定（desktop_app 上报）：system≈面试官，mic≈应聘者
SOURCE_ACTIVITY_FRESH_SECONDS = 1.2
SOURCE_TAKEOVER_CLOSE_WINDOW_SECONDS = 1.8


def _normalize_text(text: str) -> str:
    return " ".join((text or "").strip().lower().split())


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


# Fix 5: _is_question_like 已迁移到 intent.py 并以 is_question_like 公开，此处不再重复定义


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
    trace_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
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
    voiceprint_tracker = VoiceprintTracker(
        min_rms=TURN_ACTIVE_AUDIO_RMS,
        # 提高 assign_threshold：让声纹原型切换更难触发，减少误切
        # 默认 0.30，提高到 0.45 以容忍同一人的音量/语调波动
        assign_threshold=0.45,
    )
    last_dominant_speaker = None
    last_speaker_change_ts = 0.0
    # 声纹确认帧机制：连续出现同一候选 speaker 才算切换
    _speaker_candidate: int | None = None
    _speaker_candidate_count: int = 0
    _speaker_candidate_last_ts: float = 0.0
    # ASR 全局累积文本（豆包单一 session 不断追加）
    # 每次 turn 创建时快照当前值，用于提取「本轮增量文本」
    _asr_global_text: str = ""
    # 客户端音源活跃度：dominant_source in {mic, system, mixed, none}
    source_activity = {
        "dominant_source": "unknown",
        "mic_rms": 0,
        "system_rms": 0,
        "ts": 0.0,
        "change_ts": 0.0,
    }
    # tracing state
    trace_seq = 0
    last_new_turn_eval = {"trigger": False, "reason": "init"}
    # 主 ASR 稳定性监控：若持续活跃音频但长期没有文本回调，则触发重连
    main_active_frames_since_text = 0
    main_last_text_ts = 0.0
    last_main_asr_restart_ts = 0.0

    # We will need the event loop for the async callback
    loop = asyncio.get_running_loop()

    def _trace(event: str, **fields):
        nonlocal trace_seq
        if not TRACE_ENABLED:
            return
        trace_seq += 1
        payload = {
            "trace_id": trace_id,
            "session_id": session_id,
            "seq": trace_seq,
            "event": event,
            "mono_ts": round(time.monotonic(), 3),
        }
        payload.update(fields)
        try:
            print("[Trace] " + json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            print(f"[Trace] {event} {fields}")

    _trace("ws_session_started")

    class _NoopASR:
        """ASR 不可用时的占位实现，保持会话不断开。"""

        last_speaker_id = None
        last_speaker_name = None

        def set_callback(self, callback, loop):
            return

        def start(self):
            return

        def add_audio(self, chunk: bytes):
            return

        def stop(self):
            return

    asr_warning_last_ts = 0.0

    async def _notify_asr_unavailable(message: str):
        nonlocal asr_warning_last_ts
        now = time.monotonic()
        if (now - asr_warning_last_ts) < 6.0:
            return
        asr_warning_last_ts = now
        with suppress(Exception):
            await websocket.send_json(
                {
                    "type": "incremental",
                    "text": message,
                    "speaker_role": "interviewer",
                    "trace_id": trace_id,
                }
            )

    def _create_turn(
        text: str, normalized: str, now_ts: float, speaker_id: int | None = None
    ):
        nonlocal next_turn_id, _asr_global_text
        # 记录本轮开始时的 ASR 全局累积文本作为基线
        # 之后 on_text_update 收到的文本扣掉此基线，得到「本轮增量内容」
        baseline = _asr_global_text
        turn = {
            "id": next_turn_id,
            "text": text,
            "norm": normalized,
            "asr_baseline": baseline,  # ASR 文本基线（全局累积）
            "created_ts": now_ts,
            "audio_last_ts": now_ts,
            "text_last_ts": now_ts,
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
        if getattr(asr_processor, "last_speaker_id", None) is not None:
            return getattr(asr_processor, "last_speaker_id")
        speaker_id = voiceprint_tracker.dominant_speaker(now_ts)
        if speaker_id is not None:
            return speaker_id
        return last_dominant_speaker

    def _current_source_role(now_ts: float) -> str:
        # 听悟模式下：直接采用端到端的角色识别
        speaker_name = getattr(asr_processor, "last_speaker_name", None)
        if speaker_name in ["interviewer", "candidate"]:
            return speaker_name

        # 兼容旧逻辑/豆包模式下的本地音量反馈
        last_ts = float(source_activity.get("ts", 0.0) or 0.0)
        if last_ts <= 0 or (now_ts - last_ts) > SOURCE_ACTIVITY_FRESH_SECONDS:
            return "unknown"
        dominant = str(source_activity.get("dominant_source", "unknown"))
        if dominant == "system":
            return "interviewer"
        if dominant == "mic":
            return "candidate"
        return "unknown"

    def _should_start_new_turn(
        turn: dict, incoming_norm: str, now_ts: float, incoming_speaker: int | None
    ) -> bool:
        nonlocal last_new_turn_eval
        if not turn or turn.get("closed"):
            last_new_turn_eval = {"trigger": False, "reason": "no_turn"}
            return False
        prev_norm = turn.get("norm", "")
        speaker_switched = _is_speaker_switched(turn, incoming_speaker)
        speech_gap = now_ts - turn.get("audio_last_ts", now_ts)
        source_role = _current_source_role(now_ts)

        if source_role == "candidate":
            last_new_turn_eval = {
                "trigger": False,
                "reason": "candidate_source_active",
                "sim": None,
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return False

        if len(prev_norm) < 10 or len(incoming_norm) < 6:
            if speaker_switched and turn.get("got_final") and len(incoming_norm) >= 4:
                last_new_turn_eval = {
                    "trigger": True,
                    "reason": "short_text_speaker_switched",
                    "sim": None,
                    "speech_gap": round(speech_gap, 3),
                    "speaker_switched": speaker_switched,
                    "source_role": source_role,
                }
                return True
            last_new_turn_eval = {
                "trigger": False,
                "reason": "short_text_not_ready",
                "sim": None,
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return False

        sim = _similarity(incoming_norm, prev_norm)

        # 1. 声纹切换 + 相似度低 + 语隙
        if (
            speaker_switched
            and sim <= VOICEPRINT_SWITCH_SIMILARITY_THRESHOLD
            and speech_gap >= VOICEPRINT_SWITCH_MIN_GAP_SECONDS
        ):
            last_new_turn_eval = {
                "trigger": True,
                "reason": "speaker_switch_gap",
                "sim": round(sim, 3),
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return True

        # 2. 文本语义差异极大的兜底（Fix 5 增强）
        if (
            sim < NEW_QUESTION_SIMILARITY_THRESHOLD
            and incoming_norm not in prev_norm
            and prev_norm not in incoming_norm
            and (is_question_like(incoming_norm) or is_question_like(prev_norm))
            and speech_gap >= 0.22
        ):
            last_new_turn_eval = {
                "trigger": True,
                "reason": "low_similarity_question_like",
                "sim": round(sim, 3),
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return True

        # 3. 如果是非常相似的延续，禁止切分
        if sim >= NEW_QUESTION_SIMILARITY_THRESHOLD and not speaker_switched:
            last_new_turn_eval = {
                "trigger": False,
                "reason": "similar_text",
                "sim": round(sim, 3),
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return False

        # 4. 已有句末标识 —— 只在同时满足额外条件时才切换，防止每句末都误切
        # 情况A：说话人已切换（真正换人了）
        # 情况B：内容具有问题特征 + 有足够的停顿（面试官问完了）
        if turn.get("got_final"):
            if speaker_switched:
                last_new_turn_eval = {
                    "trigger": True,
                    "reason": "got_final_speaker_switched",
                    "sim": round(sim, 3),
                    "speech_gap": round(speech_gap, 3),
                    "speaker_switched": speaker_switched,
                    "source_role": source_role,
                }
                return True
            if is_question_like(turn.get("text", "")) and speech_gap >= 0.4:
                last_new_turn_eval = {
                    "trigger": True,
                    "reason": "got_final_question_like_pause",
                    "sim": round(sim, 3),
                    "speech_gap": round(speech_gap, 3),
                    "speaker_switched": speaker_switched,
                    "source_role": source_role,
                }
                return True
            # got_final 但不满足以上条件，继续等待更明确的信号
            last_new_turn_eval = {
                "trigger": False,
                "reason": "got_final_wait_more_signal",
                "sim": round(sim, 3),
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return False

        # 5. 问题特征词 + 较大的停顿
        if is_question_like(turn.get("text", "")) and speech_gap >= 0.55:
            last_new_turn_eval = {
                "trigger": True,
                "reason": "question_like_pause",
                "sim": round(sim, 3),
                "speech_gap": round(speech_gap, 3),
                "speaker_switched": speaker_switched,
                "source_role": source_role,
            }
            return True

        last_new_turn_eval = {
            "trigger": False,
            "reason": "not_enough_signal",
            "sim": round(sim, 3),
            "speech_gap": round(speech_gap, 3),
            "speaker_switched": speaker_switched,
            "source_role": source_role,
        }
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
                    "trace_id": trace_id,
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
                    "trace_id": trace_id,
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
                "trace_id": trace_id,
            }
        )

    def _schedule_answer(question_text: str, source: str, question_id=None):
        nonlocal next_answer_seq
        answer_seq = next_answer_seq
        next_answer_seq += 1
        _trace(
            "answer_scheduled",
            seq=answer_seq,
            source=source,
            question_id=question_id,
            question_preview=(question_text or "")[:80],
        )

        async def _do_answer(
            seq: int, question_snapshot: str, source_snapshot: str, qid
        ):
            nonlocal session_transcript
            try:
                _trace(
                    "answer_generation_start",
                    seq=seq,
                    source=source_snapshot,
                    question_id=qid,
                )
                async with answer_generation_lock:
                    answer = await _call_with_timeout(
                        llm_processor.generate_answer(
                            jd=JD_TEXT, resume=RESUME_TEXT, question=question_snapshot
                        ),
                        timeout_seconds=LLM_ANSWER_TIMEOUT_SECONDS,
                        fallback_text=ANSWER_FALLBACK_TEXT,
                    )
                print(f"[LLM] Answer(seq={seq}): {answer}")
                _trace(
                    "answer_generation_done",
                    seq=seq,
                    source=source_snapshot,
                    question_id=qid,
                    answer_len=len(answer or ""),
                )
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
        # Fix 2: 使用 audio_last_ts 计算真实沉默，而非 text_last_ts
        silence = now_ts - turn.get("audio_last_ts", now_ts)
        dominant_speaker = _current_dominant_speaker(now_ts)
        speaker_switched = _is_speaker_switched(turn, dominant_speaker)
        source_role = _current_source_role(now_ts)

        # Fix 4: 声纹增强关闭逻辑
        # 条件：说话人明确切换（非同一人） + 本轮内容足够长 + 沉默达阈值
        voiceprint_close = (
            speaker_switched
            and len(turn.get("norm", "")) >= 10
            and silence >= VOICEPRINT_CLOSE_SILENCE_SECONDS
            and (now_ts - last_speaker_change_ts) <= 2.0
        )
        # 音源接管关闭：当前明确是候选人说话，说明面试官提问通常已经结束。
        source_takeover_close = (
            source_role == "candidate"
            and len(turn.get("norm", "")) >= 8
            and (now_ts - float(source_activity.get("change_ts", 0.0) or 0.0))
            <= SOURCE_TAKEOVER_CLOSE_WINDOW_SECONDS
        )

        should_close = (
            force
            or (
                # 正常沉默关闭：已收到 ASR 句末信号，或文本包含问题信号词
                silence >= QUESTION_CLOSE_SILENCE_SECONDS
                and (turn.get("got_final") or is_question_like(turn.get("text", "")))
            )
            or voiceprint_close  # Fix 4: 声纹换人强制关闭
            or source_takeover_close
            or silence >= QUESTION_FORCE_CLOSE_SECONDS  # 兜底强制关闭
        )
        is_q_like = is_question_like(turn.get("text", ""))
        close_eval = {
            "turn_id": turn_id,
            "reason": reason,
            "force": bool(force),
            "silence": round(silence, 3),
            "got_final": bool(turn.get("got_final")),
            "is_question_like": bool(is_q_like),
            "voiceprint_close": bool(voiceprint_close),
            "source_takeover_close": bool(source_takeover_close),
            "source_role": source_role,
            "speaker_switched": bool(speaker_switched),
            "dominant_speaker": dominant_speaker,
        }
        if not should_close:
            # silence 轮询会非常频繁，这里采样打印；其它原因则全量打印。
            if reason != "silence":
                _trace("turn_close_skipped", **close_eval)
            else:
                turn["close_check_count"] = int(turn.get("close_check_count", 0)) + 1
                if turn["close_check_count"] % 8 == 1:
                    _trace("turn_close_poll", **close_eval)
            return False

        close_log = (
            f"reason={reason}  silence={silence:.2f}s  "
            f"got_final={turn.get('got_final')}  "
            f"voiceprint_close={voiceprint_close}  "
            f"source_takeover_close={source_takeover_close}  "
            f"speaker_switched={speaker_switched}  "
            f"dominant_speaker={dominant_speaker}"
        )
        print(f"[Turn] 关闭 turn={turn_id}  {close_log}")
        _trace("turn_closed", **close_eval)

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
            _trace(
                "turn_answer_skipped_duplicate",
                turn_id=turn_id,
                normalized=normalized[:80],
            )
            current_turn = None
            return True

        last_answer_trigger_text = normalized
        last_answer_trigger_ts = now_ts
        _schedule_answer(turn.get("text", ""), source="asr", question_id=turn.get("id"))
        current_turn = None
        return True

    def _arm_close_check(turn_id: int):
        """Fix 3: 用单一长驻轮询协程替代递归 Task，彻底消除 Task 堆积问题。"""
        nonlocal close_check_task
        if close_check_task and not close_check_task.done():
            close_check_task.cancel()

        async def _watcher():
            """持续轮询关闭条件，直到 turn 被关闭或取消。"""
            try:
                while True:
                    await asyncio.sleep(CLOSE_WATCHER_POLL_SECONDS)
                    if not current_turn or current_turn.get("id") != turn_id:
                        break
                    if current_turn.get("closed"):
                        break
                    closed = await _maybe_close_turn(turn_id, reason="silence")
                    if closed:
                        break
            except asyncio.CancelledError:
                return

        close_check_task = asyncio.create_task(_watcher())
        background_tasks.add(close_check_task)
        close_check_task.add_done_callback(background_tasks.discard)

    trace_seq = 0

    # 双通道特性：独立的候选人 ASR 会议
    asr_candidate = None
    candidate_last_start_attempt_ts = 0.0

    def _ensure_asr_candidate():
        nonlocal asr_candidate, candidate_last_start_attempt_ts
        if asr_candidate is None:
            now = time.monotonic()
            if (
                candidate_last_start_attempt_ts > 0
                and (now - candidate_last_start_attempt_ts)
                < CANDIDATE_ASR_RETRY_SECONDS
            ):
                return
            candidate_last_start_attempt_ts = now
            print("[ASR] Initializing dedicated Candidate ASR session...")
            asr_candidate = get_asr_processor()
            asr_candidate.set_callback(
                on_candidate_text_update, asyncio.get_running_loop()
            )
            try:
                asr_candidate.start()
            except Exception as e:
                print(f"[ASR] Failed to start Candidate ASR: {e}")
                _trace("candidate_asr_start_failed", error=str(e))
                asr_candidate = None

    async def on_candidate_text_update(text: str, is_sentence_end: bool):
        """专用于候选人音频通道的回调，仅做字幕展示和转写记录，不干扰主流程"""
        if not text:
            return

        print(f"[Callback-Candidate] Received: {text} (is_end={is_sentence_end})")

        # 为了展示，仍然发送给前端
        # 由于我们这里没有 "current_turn"，每次当做独立的增量（或全量覆盖）
        # 简单起见，利用独立的 trace_id 或直接发送
        await websocket.send_json(
            {
                "type": "incremental",
                "text": text,
                "question_id": -1,  # 使用固定的或特殊的 ID 表示独立的候选人流
                "speaker_id": None,
                "speaker_role": "candidate",
                "trace_id": f"{trace_id}-cand",
            }
        )
        _trace(
            "ws_incremental_sent",
            stream="candidate",
            speaker_role="candidate",
            question_id=-1,
            text_preview=text[:80],
        )

        if is_sentence_end:
            print(f"[Candidate-ASR] Final: {text}")
            session_transcript.append(
                {
                    "seq": len(session_transcript) + 1,
                    "source": "candidate_channel",
                    "question_id": -1,
                    "面试官的问题": "",
                    "AI参考回答": "",
                    "候选人回答": text,
                }
            )

    speaker_mapping_state = {}

    async def on_text_update(text: str, is_sentence_end: bool):
        """Callback fired by the ASR processor when new text is recognized."""
        nonlocal current_turn, outline_task, _asr_global_text
        nonlocal main_active_frames_since_text, main_last_text_ts
        if not text:
            return

        print(f"[Callback-Main] Received: {text} (is_end={is_sentence_end})")

        # 记录豆包 ASR 返回的全局累积文本
        _asr_global_text = text

        def _extract_increment(full_text: str, baseline: str) -> str:
            """从 ASR 全局累积文本中提取本轮新增内容。"""
            bl = baseline.strip()
            ft = full_text.strip()
            if not bl:
                return ft
            if ft.startswith(bl):
                inc = ft[len(bl) :].strip()
                return inc if inc else ft
            # ASR 重识别导致全文变化，取最后一句作为增量兜底
            parts = [s.strip() for s in ft.replace("，", "。").split("。") if s.strip()]
            return parts[-1] if parts else ft

        now_ts = time.monotonic()
        main_last_text_ts = now_ts
        main_active_frames_since_text = 0
        normalized = _normalize_text(text)
        # incoming_speaker = _current_dominant_speaker(now_ts)
        # source_role = _current_source_role(now_ts)

        # 1. 摒弃本地音源判定，全量使用云端 speaker_id
        incoming_speaker = getattr(asr_processor, "last_speaker_id", None)
        speaker_name = getattr(asr_processor, "last_speaker_name", None)

        if speaker_name in ["interviewer", "candidate"]:
            speaker_mapping_state[incoming_speaker] = speaker_name
            source_role = speaker_name
        else:
            # 默认兜底机制：如果没有 Name，先将当前说话人暂定为 interviewer 以保证文本能在前端展示
            source_role = speaker_mapping_state.get(incoming_speaker, "interviewer")

        _trace(
            "asr_text_update",
            current_turn_id=(current_turn.get("id") if current_turn else None),
            is_sentence_end=bool(is_sentence_end),
            speaker_id=incoming_speaker,
            source_role=source_role,
            text_preview=text[:80],
            text_len=len(normalized),
        )

        # 候选人音源主导时，跳过"问题识别"链路，避免把回答当成下一题。
        # 2. 取消静默拦截：无论是候选人还是面试官说话，所有增量文本 (incremental) 必须无脑广播给前端
        if source_role == "candidate":
            # 提取候选人增量文本用于字幕
            candidate_text = text  # 默认用原始文本
            if current_turn:
                baseline = current_turn.get("asr_baseline", "")
                candidate_text = _extract_increment(text, baseline) or text
            try:
                await websocket.send_json(
                    {
                        "type": "incremental",
                        "text": candidate_text,
                        "question_id": current_turn.get("id") if current_turn else None,
                        "speaker_id": incoming_speaker,
                        "speaker_role": "candidate",
                        "trace_id": trace_id,
                    }
                )
                _trace(
                    "ws_incremental_sent",
                    stream="main",
                    speaker_role="candidate",
                    question_id=(current_turn.get("id") if current_turn else None),
                    text_preview=(candidate_text or text)[:80],
                )
            except Exception:
                pass

            if current_turn and not current_turn.get("closed"):
                force_close = bool(
                    current_turn.get("got_final")
                    or is_question_like(current_turn.get("text", ""))
                )
                await _maybe_close_turn(
                    current_turn.get("id"),
                    reason="candidate_takeover",
                    force=force_close,
                )
            _trace(
                "candidate_text_ignored",
                current_turn_id=(current_turn.get("id") if current_turn else None),
                is_sentence_end=bool(is_sentence_end),
                text_preview=text[:80],
            )
            return

        if current_turn and _should_start_new_turn(
            current_turn, normalized, now_ts, incoming_speaker
        ):
            _trace(
                "new_turn_detected",
                prev_turn_id=current_turn.get("id"),
                **last_new_turn_eval,
            )
            await _maybe_close_turn(
                current_turn.get("id"), reason="next_question_start", force=True
            )
        elif current_turn:
            _trace(
                "new_turn_not_detected",
                prev_turn_id=current_turn.get("id"),
                **last_new_turn_eval,
            )

        if not current_turn:
            current_turn = _create_turn(text, normalized, now_ts, incoming_speaker)
            _trace(
                "turn_created",
                turn_id=current_turn.get("id"),
                speaker_id=current_turn.get("speaker_id"),
                text_preview=text[:80],
            )
        else:
            # 提取本轮增量文本（消除 ASR 全局累积污染）
            baseline = current_turn.get("asr_baseline", "")
            increment_text = _extract_increment(text, baseline)
            increment_norm = _normalize_text(increment_text)

            if increment_norm != current_turn.get("norm"):
                current_turn["text_last_ts"] = now_ts

            # 只用增量文本更新本轮内容
            current_turn["text"] = increment_text
            current_turn["norm"] = increment_norm
            if current_turn.get("speaker_id") is None and incoming_speaker is not None:
                current_turn["speaker_id"] = incoming_speaker

        # 用「增量文本」做归一化，供后续判定
        baseline_now = current_turn.get("asr_baseline", "")
        inc_text_now = _extract_increment(text, baseline_now)
        normalized = _normalize_text(inc_text_now) or normalized

        # 之前为了测试注释掉的代码，需恢复工作：
        # if is_sentence_end:
        #     current_turn["got_final"] = True
        #     _trace(
        #         "asr_sentence_end",
        #         turn_id=current_turn.get("id"),
        #         text_preview=(current_turn.get("text", "") or text)[:80],
        #     )
        #     # 关键：句末直接关题，不再发送 incremental。
        #     await _maybe_close_turn(
        #         current_turn.get("id"), reason="asr_final", force=True
        #     )
        #     return

        # Send incremental text with question_id for debug/traceability.
        # 注意：发送「本轮增量文本」而非 ASR 全局累积文本，
        # 避免前端字幕不断重复全量历史。
        try:
            await websocket.send_json(
                {
                    "type": "incremental",
                    "text": current_turn.get("text", "") or text,
                    "question_id": current_turn.get("id"),
                    "speaker_id": incoming_speaker,
                    "speaker_role": source_role,
                    "trace_id": trace_id,
                }
            )
            _trace(
                "ws_incremental_sent",
                stream="main",
                speaker_role=source_role,
                question_id=current_turn.get("id"),
                text_preview=(current_turn.get("text", "") or text)[:80],
            )
        except Exception:
            pass

        if is_sentence_end:
            current_turn["got_final"] = True
            _trace(
                "asr_sentence_end",
                turn_id=current_turn.get("id"),
                text_preview=(current_turn.get("text", "") or text)[:80],
            )
            # 听悟虽然判断了句子结束（VAD停顿），业务仍然执行原有的强制关闭触发。
            # 若后续发现切分过碎可去掉 force=True 让外部任务管理。
            await _maybe_close_turn(
                current_turn.get("id"), reason="asr_final", force=True
            )
            return

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
            _trace(
                "outline_triggered",
                turn_id=turn_id,
                seq=outline_seq,
                text_preview=text[:80],
            )

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
                            "trace_id": trace_id,
                        }
                    )
                except Exception as e:
                    print(f"[WS] Error sending outline: {e}")

            outline_task = asyncio.create_task(_do_outline(text, outline_seq, turn_id))
            background_tasks.add(outline_task)
            outline_task.add_done_callback(background_tasks.discard)

        _arm_close_check(current_turn.get("id"))

    async def _start_main_asr_with_fallback(reason: str) -> bool:
        """启动主 ASR。听悟失败时自动回退豆包；都失败则降级为手动模式。"""
        nonlocal asr_processor
        provider = get_asr_processor()
        provider_name = provider.__class__.__name__
        provider.set_callback(on_text_update, loop)
        try:
            provider.start()
            asr_processor = provider
            _trace("asr_started", reason=reason, provider=provider_name)
            return True
        except Exception as primary_err:
            print(f"[ASR] Failed to start ASR({provider_name}): {primary_err}")
            _trace(
                "asr_start_failed",
                reason=reason,
                provider=provider_name,
                error=str(primary_err),
            )

        if isinstance(provider, TingwuProvider):
            fallback = DoubaoProvider()
            fallback_name = fallback.__class__.__name__
            fallback.set_callback(on_text_update, loop)
            try:
                fallback.start()
                asr_processor = fallback
                _trace(
                    "asr_fallback_started",
                    reason=reason,
                    from_provider=provider_name,
                    to_provider=fallback_name,
                )
                await _notify_asr_unavailable(
                    "⚠️ 听悟连接失败，已自动切换备用语音识别。"
                )
                return True
            except Exception as fallback_err:
                print(
                    f"[ASR] Fallback start failed ({provider_name}->{fallback_name}): {fallback_err}"
                )
                _trace(
                    "asr_fallback_failed",
                    reason=reason,
                    from_provider=provider_name,
                    to_provider=fallback_name,
                    error=str(fallback_err),
                )

        asr_processor = _NoopASR()
        await _notify_asr_unavailable(
            "⚠️ 语音识别暂不可用（网络/证书异常）。你仍可在输入框手动提问。"
        )
        return False

    # Initialize and start ASR stream (per-connection instance; do not share globally)
    asr_processor = _NoopASR()
    asr_available = await _start_main_asr_with_fallback(reason="session_init")
    if not asr_available:
        print("[ASR] Main ASR unavailable for this session; manual mode only.")

    try:
        _recv_count = 0
        while True:
            # Receive audio chunk (binary) or command (text)
            message = await websocket.receive()

            # [HOTFIX DEBUG]: 把 message 结构打出来看看
            if "bytes" in message:
                if _recv_count % 100 == 1:
                    print(
                        f"[WS-DEBUG] ASGI received dict with 'bytes' length: {len(message.get('bytes', b''))}"
                    )
            elif "text" in message:
                txt = message["text"]
                if '"source_activity"' not in txt:
                    print(f"[WS-DEBUG] ASGI received dict with 'text': {txt[:80]}")

            data_bytes = None
            is_candidate_channel = False

            if "bytes" in message and message["bytes"] is not None:
                data_bytes = message["bytes"]
            elif "text" in message:
                text_data = message["text"]
                try:
                    cmd_json = json.loads(text_data)
                    # 支持双通道 JSON 音频协议
                    if cmd_json.get("type") == "audio":
                        # {"type": "audio", "channel": "...", "data": "<base64>"}
                        b64_data = cmd_json.get("data", "")
                        channel = cmd_json.get("channel", "")
                        if b64_data:
                            try:
                                data_bytes = base64.b64decode(b64_data)
                                if channel in ("candidate", "mic"):
                                    is_candidate_channel = True
                                elif channel in ("interviewer", "system"):
                                    # 显式强化系统音源身份
                                    source_activity["dominant_source"] = "system"
                            except Exception as e:
                                print(f"[WS] Audio decode failed: {e}")
                                print(f"[WS] Base64 decode error: {e}")

                    elif cmd_json.get("command") == "end_session":
                        _trace("command_end_session")
                        print(
                            f"[Memory] Session ended by user. Generating analysis for: {session_id}"
                        )
                        # Stop both ASRs
                        asr_processor.stop()
                        if asr_candidate:
                            asr_candidate.stop()

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

                        # 等待已触发但未完成的回答任务
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
                            {
                                "type": "analysis",
                                "answer": analysis,
                                "trace_id": trace_id,
                            }
                        )
                        break

                    elif cmd_json.get("command") == "source_activity":
                        now_ts = time.monotonic()
                        dominant = str(
                            cmd_json.get(
                                "dominant_source",
                                source_activity.get("dominant_source", "unknown"),
                            )
                        )
                        prev_dominant = str(
                            source_activity.get("dominant_source", "unknown")
                        )
                        source_activity["dominant_source"] = dominant
                        source_activity["mic_rms"] = int(
                            cmd_json.get("mic_rms", 0) or 0
                        )
                        source_activity["system_rms"] = int(
                            cmd_json.get("system_rms", 0) or 0
                        )
                        source_activity["ts"] = now_ts
                        if dominant != prev_dominant:
                            source_activity["change_ts"] = now_ts
                        _trace(
                            "source_activity",
                            dominant_source=dominant,
                            mic_rms=source_activity["mic_rms"],
                            system_rms=source_activity["system_rms"],
                            changed=(dominant != prev_dominant),
                        )

                    elif cmd_json.get("command") == "manual_question":
                        manual_text = cmd_json.get("text", "").strip()
                        if manual_text:
                            _trace(
                                "command_manual_question",
                                text_preview=manual_text[:80],
                            )
                            print(f"[Manual] User sent: {manual_text}")
                            if close_check_task and not close_check_task.done():
                                close_check_task.cancel()
                            if current_turn and not current_turn.get("closed"):
                                await _maybe_close_turn(
                                    current_turn.get("id"),
                                    reason="manual_takeover",
                                    force=True,
                                )
                            # Create mock turn for manual question.
                            manual_turn_id = next_turn_id
                            next_turn_id += 1
                            session_transcript.append(
                                {
                                    "seq": len(session_transcript) + 1,
                                    "source": "manual",
                                    "question_id": manual_turn_id,
                                    "面试官的问题": manual_text,
                                    "AI参考回答": "",
                                }
                            )
                            await websocket.send_json(
                                {
                                    "type": "incremental",
                                    "text": f"🙋 {manual_text}",
                                    "question_id": manual_turn_id,
                                    "speaker_id": 999,
                                    "speaker_role": "interviewer",
                                    "trace_id": trace_id,
                                }
                            )
                            _schedule_answer(manual_text, "manual", manual_turn_id)
                        continue  # Add continue to prevent falling through

                except json.JSONDecodeError:
                    print("[WS] Ignored invalid JSON command.")
                    continue

            if data_bytes is not None:
                data = data_bytes
                now_ts = time.monotonic()
                _recv_count += 1

                # 双路分支处理
                if is_candidate_channel:
                    if _recv_count % 100 == 1:
                        print(f"[WS] Candidate audio frame size={len(data)}B")
                    _ensure_asr_candidate()
                    if asr_candidate is not None:
                        asr_candidate.add_audio(data)
                    elif _recv_count % 60 == 1:
                        _trace(
                            "candidate_asr_unavailable_drop",
                            frame_bytes=len(data),
                            recv_count=_recv_count,
                        )
                    # 不参与主路录音 wave_file、不参与主路的音频活跃/声纹检测
                    continue

                if _recv_count % 100 == 1:
                    print(f"[WS] Main audio frame #{_recv_count} size={len(data)}B")
                # Save to disk
                wave_file.writeframes(data)
                # Stream to main ASR
                asr_processor.add_audio(data)
                sid = voiceprint_tracker.update_audio(data, ts=now_ts)
                # 声纹确认帧机制：连续 SPEAKER_CONFIRM_FRAMES 帧才算切换，防止噪声误触
                if sid is not None:
                    gap = now_ts - _speaker_candidate_last_ts
                    if (
                        sid == _speaker_candidate
                        and gap <= SPEAKER_CONFIRM_MAX_GAP_SECONDS
                    ):
                        _speaker_candidate_count += 1
                    else:
                        # 候选变为 sid，重新计数
                        _speaker_candidate = sid
                        _speaker_candidate_count = 1
                    _speaker_candidate_last_ts = now_ts

                    # 只有连续确认帧才真正更新 dominant_speaker
                    if _speaker_candidate_count >= SPEAKER_CONFIRM_FRAMES:
                        confirmed_speaker = _speaker_candidate
                        dominant = voiceprint_tracker.dominant_speaker(now_ts)
                        if (
                            confirmed_speaker is not None
                            and confirmed_speaker != last_dominant_speaker
                        ):
                            print(
                                f"[Voiceprint] Speaker confirmed: {last_dominant_speaker} → {confirmed_speaker} (frames={_speaker_candidate_count})"
                            )
                            last_dominant_speaker = confirmed_speaker
                            last_speaker_change_ts = now_ts
                # 只在“有效语音”时刷新沉默计时，避免底噪导致永不关题。
                is_active_audio = sid is not None
                rms = 0
                if not is_active_audio:
                    try:
                        rms = audioop.rms(data, 2)
                        is_active_audio = rms >= TURN_ACTIVE_AUDIO_RMS
                        # if rms > 100: # 偶尔监控一下底噪
                        #     print(f"[Audio-Debug] rms={rms} is_active={is_active_audio}")
                    except audioop.error:
                        is_active_audio = False
                else:
                    try:
                        rms = audioop.rms(data, 2)
                    except audioop.error:
                        rms = 0

                if current_turn and not current_turn.get("closed") and is_active_audio:
                    current_turn["audio_last_ts"] = now_ts
                if is_active_audio:
                    main_active_frames_since_text += 1
                # 主 ASR 疑似卡死：持续活跃音频但长期无文本回调，尝试自动重启。
                source_role_now = _current_source_role(now_ts)
                if (
                    is_active_audio
                    and source_role_now != "candidate"
                    and main_active_frames_since_text >= ASR_STALL_ACTIVE_FRAMES
                    and (now_ts - last_main_asr_restart_ts)
                    >= ASR_RESTART_COOLDOWN_SECONDS
                ):
                    since_last_text = (
                        now_ts - main_last_text_ts if main_last_text_ts > 0 else None
                    )
                    _trace(
                        "asr_stall_detected",
                        recv_count=_recv_count,
                        active_frames_since_text=main_active_frames_since_text,
                        since_last_text=(
                            round(since_last_text, 3)
                            if since_last_text is not None
                            else None
                        ),
                        source_role=source_role_now,
                        rms=rms,
                        turn_id=(current_turn.get("id") if current_turn else None),
                    )
                    try:
                        asr_processor.stop()
                    except Exception:
                        pass
                    restarted = await _start_main_asr_with_fallback(
                        reason="stall_restart"
                    )
                    main_active_frames_since_text = 0
                    last_main_asr_restart_ts = now_ts
                    if restarted:
                        _trace("asr_restarted", recv_count=_recv_count)
                    else:
                        _trace("asr_restart_failed", recv_count=_recv_count)
                elif current_turn and not current_turn.get("closed"):
                    # 如果不是 active audio，观察一下静默累计
                    silence = now_ts - current_turn.get("audio_last_ts", now_ts)
                    if silence >= 0.7:
                        # 只有在较长静默时才打印，避免刷屏
                        if _recv_count % 50 == 0:
                            print(
                                f"[Audio-Silence] turn={current_turn.get('id')} silence={silence:.2f}s"
                            )
                if _recv_count % max(1, TRACE_AUDIO_SAMPLE_EVERY) == 1:
                    _trace(
                        "audio_frame",
                        recv_count=_recv_count,
                        turn_id=(current_turn.get("id") if current_turn else None),
                        speaker_id=sid,
                        dominant_speaker=last_dominant_speaker,
                        active_audio=bool(is_active_audio),
                        rms=rms,
                        frame_bytes=len(data),
                    )
    except WebSocketDisconnect:
        _trace("ws_client_disconnected")
        print("[WS] Client disconnected")
    except Exception as e:
        _trace("ws_error", error=str(e))
        print(f"[WS] Error: {e}")
    finally:
        _trace("ws_session_finalizing", transcript_size=len(session_transcript))
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
