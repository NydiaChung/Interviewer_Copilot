"""WebSocket 入口：accept → receive loop → cleanup。"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
import wave
from contextlib import suppress
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

from server.asr import DoubaoProvider, TingwuProvider, get_asr_processor
from server.asr.base import ASRProvider
from server.config import CANDIDATE_ASR_RETRY_SECONDS
from server.handlers.asr_callback import (
    build_candidate_callback,
    build_text_callback,
)
from server.handlers.audio_processor import process_audio_frame
from server.handlers.command_handler import handle_command
from server.models.connection import ConnectionState
from server.models.session import InterviewSession
from server.utils.tracing import Tracer


# ---------------------------------------------------------------------------
# 会话容器（原型级单体模式）
# ---------------------------------------------------------------------------
_active_sessions: dict[str, InterviewSession] = {}


def get_default_session() -> InterviewSession:
    session_id = "default_session"
    if session_id not in _active_sessions:
        _active_sessions[session_id] = InterviewSession(session_id)
    return _active_sessions[session_id]


# ---------------------------------------------------------------------------
# Noop ASR（降级占位）
# ---------------------------------------------------------------------------
class _NoopASR(ASRProvider):
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


# ---------------------------------------------------------------------------
# ASR 启动 + Fallback
# ---------------------------------------------------------------------------
async def _notify_asr_unavailable(ctx: ConnectionState, message: str):
    now = time.monotonic()
    if (now - getattr(ctx, "_asr_warning_last_ts", 0.0)) < 6.0:
        return
    ctx._asr_warning_last_ts = now
    with suppress(Exception):
        await ctx.websocket.send_json(
            {
                "type": "incremental",
                "text": message,
                "speaker_role": "interviewer",
                "trace_id": ctx.trace_id,
            }
        )


async def start_main_asr_with_fallback(
    ctx: ConnectionState, reason: str
) -> bool:
    """启动主 ASR，听悟失败自动回退豆包，都失败降级手动模式。"""
    provider = get_asr_processor()
    provider_name = provider.__class__.__name__
    on_text = build_text_callback(ctx)
    provider.set_callback(on_text, ctx.loop)
    try:
        provider.start()
        ctx.asr_processor = provider
        ctx.trace("asr_started", reason=reason, provider=provider_name)
        return True
    except Exception as primary_err:
        print(f"[ASR] Failed to start ASR({provider_name}): {primary_err}")
        ctx.trace(
            "asr_start_failed",
            reason=reason,
            provider=provider_name,
            error=str(primary_err),
        )

    if isinstance(provider, TingwuProvider):
        fallback = DoubaoProvider()
        fallback_name = fallback.__class__.__name__
        fallback.set_callback(on_text, ctx.loop)
        try:
            fallback.start()
            ctx.asr_processor = fallback
            ctx.trace(
                "asr_fallback_started",
                reason=reason,
                from_provider=provider_name,
                to_provider=fallback_name,
            )
            await _notify_asr_unavailable(
                ctx, "⚠️ 听悟连接失败，已自动切换备用语音识别。"
            )
            return True
        except Exception as fallback_err:
            print(
                f"[ASR] Fallback start failed "
                f"({provider_name}->{fallback_name}): {fallback_err}"
            )
            ctx.trace(
                "asr_fallback_failed",
                reason=reason,
                from_provider=provider_name,
                to_provider=fallback_name,
                error=str(fallback_err),
            )

    ctx.asr_processor = _NoopASR()
    await _notify_asr_unavailable(
        ctx, "⚠️ 语音识别暂不可用（网络/证书异常）。你仍可在输入框手动提问。"
    )
    return False


def _ensure_asr_candidate(ctx: ConnectionState):
    """确保候选人专用 ASR 已启动。"""
    if ctx.asr_candidate is not None:
        return
    now = time.monotonic()
    if (
        ctx.candidate_last_start_attempt_ts > 0
        and (now - ctx.candidate_last_start_attempt_ts)
        < CANDIDATE_ASR_RETRY_SECONDS
    ):
        return
    ctx.candidate_last_start_attempt_ts = now
    print("[ASR] Initializing dedicated Candidate ASR session...")
    candidate = get_asr_processor()
    on_cand = build_candidate_callback(ctx)
    candidate.set_callback(on_cand, ctx.loop)
    try:
        candidate.start()
        ctx.asr_candidate = candidate
    except Exception as e:
        print(f"[ASR] Failed to start Candidate ASR: {e}")
        ctx.trace("candidate_asr_start_failed", error=str(e))
        ctx.asr_candidate = None


# ---------------------------------------------------------------------------
# WebSocket 主入口
# ---------------------------------------------------------------------------
async def audio_websocket(websocket: WebSocket):
    """WebSocket 端点：音频流处理。"""
    await websocket.accept()

    # 会话初始化
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace_id = f"{session_id}-{uuid.uuid4().hex[:8]}"
    records_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server", "records")
    # 兼容：如果 server 目录就是当前的包目录
    if not os.path.isdir(records_dir):
        records_dir = os.path.join(os.path.dirname(__file__), "..", "records")
    os.makedirs(records_dir, exist_ok=True)

    audio_file_path = os.path.join(records_dir, f"session_{session_id}.wav")
    transcript_file_path = os.path.join(
        records_dir, f"session_{session_id}.json"
    )

    wave_file = wave.open(audio_file_path, "wb")
    wave_file.setnchannels(1)
    wave_file.setsampwidth(2)
    wave_file.setframerate(16000)

    session = get_default_session()
    session.transcript.clear()

    tracer = Tracer(trace_id, session_id)

    ctx = ConnectionState(
        websocket=websocket,
        session=session,
        tracer=tracer,
        session_id=session_id,
        trace_id=trace_id,
        wave_file=wave_file,
        transcript_file_path=transcript_file_path,
    )
    ctx.loop = asyncio.get_running_loop()
    ctx._asr_warning_last_ts = 0.0

    ctx.trace("ws_session_started")

    # 启动 ASR
    ctx.asr_processor = _NoopASR()
    asr_available = await start_main_asr_with_fallback(
        ctx, reason="session_init"
    )
    if not asr_available:
        print("[ASR] Main ASR unavailable; manual mode only.")

    try:
        await _receive_loop(ctx)
    except WebSocketDisconnect:
        ctx.trace("ws_client_disconnected")
        print("[WS] Client disconnected")
    except Exception as e:
        ctx.trace("ws_error", error=str(e))
        print(f"[WS] Error: {e}")
    finally:
        ctx.trace(
            "ws_session_finalizing",
            transcript_size=len(ctx.session_transcript),
        )
        ctx.asr_processor.stop()
        for task in ctx.background_tasks:
            task.cancel()
        with suppress(Exception):
            await asyncio.gather(
                *ctx.background_tasks, return_exceptions=True
            )
        wave_file.close()

        # 意外断开时保存部分 transcript
        if (
            not os.path.exists(transcript_file_path)
            and ctx.session_transcript
        ):
            with open(transcript_file_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "jd": session.jd_text,
                        "resume": session.resume_text,
                        "history": session.get_sorted_transcript(),
                        "analysis": "未正常结束，未能生成点评。",
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )


async def _receive_loop(ctx: ConnectionState):
    """主接收循环：分发音频帧和 JSON 命令。"""
    while True:
        message = await ctx.websocket.receive()

        # Debug 日志
        if "bytes" in message:
            if ctx.recv_count % 100 == 1:
                print(
                    f"[WS-DEBUG] ASGI received 'bytes' "
                    f"length: {len(message.get('bytes', b''))}"
                )
        elif "text" in message:
            txt = message["text"]
            if '"source_activity"' not in txt:
                print(f"[WS-DEBUG] ASGI received 'text': {txt[:80]}")

        data_bytes = None
        is_candidate_channel = False

        if "bytes" in message and message["bytes"] is not None:
            data_bytes = message["bytes"]
        elif "text" in message:
            text_data = message["text"]
            try:
                cmd_json = json.loads(text_data)

                # 双通道 JSON 音频
                if cmd_json.get("type") == "audio":
                    b64_data = cmd_json.get("data", "")
                    channel = cmd_json.get("channel", "")
                    if b64_data:
                        try:
                            data_bytes = base64.b64decode(b64_data)
                            if channel in ("candidate", "mic"):
                                is_candidate_channel = True
                            elif channel in ("interviewer", "system"):
                                ctx.source_activity[
                                    "dominant_source"
                                ] = "system"
                        except Exception as e:
                            print(f"[WS] Audio decode failed: {e}")
                else:
                    # JSON 命令
                    should_break = await handle_command(ctx, cmd_json)
                    if should_break:
                        break
                    continue

            except json.JSONDecodeError:
                print("[WS] Ignored invalid JSON command.")
                continue

        if data_bytes is None:
            continue

        # 双路分支
        if is_candidate_channel:
            if ctx.recv_count % 100 == 1:
                print(
                    f"[WS] Candidate audio frame size={len(data_bytes)}B"
                )
            _ensure_asr_candidate(ctx)
            if ctx.asr_candidate is not None:
                ctx.asr_candidate.add_audio(data_bytes)
            ctx.recv_count += 1
            continue

        # 主音频通道
        process_audio_frame(ctx, data_bytes)
