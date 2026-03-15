"""音频帧处理：录音、声纹更新、ASR 转发、静默检测、ASR 重启。"""

from __future__ import annotations

import audioop
import time
from typing import TYPE_CHECKING

from server.config import (
    ASR_RESTART_COOLDOWN_SECONDS,
    ASR_STALL_ACTIVE_FRAMES,
    SPEAKER_CONFIRM_FRAMES,
    SPEAKER_CONFIRM_MAX_GAP_SECONDS,
    TRACE_AUDIO_SAMPLE_EVERY,
    TURN_ACTIVE_AUDIO_RMS,
)

if TYPE_CHECKING:
    from server.models.connection import ConnectionState


def current_source_role(ctx: ConnectionState, now_ts: float) -> str:
    """判断当前说话人角色（interviewer / candidate / unknown）。"""
    from server.config import USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION

    if USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION:
        last_ts = float(ctx.source_activity.get("ts", 0.0) or 0.0)
        if last_ts > 0 and (now_ts - last_ts) <= 1.2:
            dominant = str(
                ctx.source_activity.get("dominant_source", "unknown")
            )
            if dominant == "system":
                return "interviewer"
            if dominant == "mic":
                return "candidate"

    speaker_name = getattr(ctx.asr_processor, "last_speaker_name", None)
    if speaker_name in ("interviewer", "candidate"):
        return speaker_name

    last_ts = float(ctx.source_activity.get("ts", 0.0) or 0.0)
    if last_ts <= 0 or (now_ts - last_ts) > 1.2:
        return "unknown"
    dominant = str(ctx.source_activity.get("dominant_source", "unknown"))
    if dominant == "system":
        return "interviewer"
    if dominant == "mic":
        return "candidate"
    return "unknown"


def process_audio_frame(ctx: ConnectionState, data: bytes):
    """处理一帧音频：录音、声纹、ASR、静默检测。"""
    now_ts = time.monotonic()
    ctx.recv_count += 1

    if ctx.recv_count % 100 == 1:
        print(f"[WS] Main audio frame #{ctx.recv_count} size={len(data)}B")

    # 写入 WAV
    ctx.wave_file.writeframes(data)

    # 发送给主 ASR
    ctx.asr_processor.add_audio(data)

    # 声纹更新
    sid = ctx.voiceprint_tracker.update_audio(data, ts=now_ts)
    _update_speaker_confirmation(ctx, sid, now_ts)

    # 音频活跃度判定
    is_active_audio, rms = _check_audio_activity(ctx, sid, data)

    # 更新 turn 的 audio_last_ts
    turn = ctx.turn_manager.current_turn
    if turn and not turn.get("closed") and is_active_audio:
        turn["audio_last_ts"] = now_ts

    if is_active_audio:
        ctx.main_active_frames_since_text += 1

    # ASR 疑似卡死检测
    _check_asr_stall(ctx, is_active_audio, rms, now_ts)

    # 采样 trace
    if ctx.recv_count % max(1, TRACE_AUDIO_SAMPLE_EVERY) == 1:
        ctx.trace(
            "audio_frame",
            recv_count=ctx.recv_count,
            turn_id=(turn.get("id") if turn else None),
            speaker_id=sid,
            dominant_speaker=ctx.last_dominant_speaker,
            active_audio=bool(is_active_audio),
            rms=rms,
            frame_bytes=len(data),
        )


def _update_speaker_confirmation(
    ctx: ConnectionState, sid: int | None, now_ts: float
):
    """声纹确认帧机制：连续 N 帧同一 speaker 才算切换。"""
    if sid is None:
        return
    gap = now_ts - ctx.speaker_candidate_last_ts
    if sid == ctx.speaker_candidate and gap <= SPEAKER_CONFIRM_MAX_GAP_SECONDS:
        ctx.speaker_candidate_count += 1
    else:
        ctx.speaker_candidate = sid
        ctx.speaker_candidate_count = 1
    ctx.speaker_candidate_last_ts = now_ts

    if ctx.speaker_candidate_count >= SPEAKER_CONFIRM_FRAMES:
        confirmed = ctx.speaker_candidate
        if confirmed is not None and confirmed != ctx.last_dominant_speaker:
            print(
                f"[Voiceprint] Speaker confirmed: "
                f"{ctx.last_dominant_speaker} → {confirmed} "
                f"(frames={ctx.speaker_candidate_count})"
            )
            ctx.last_dominant_speaker = confirmed
            ctx.last_speaker_change_ts = now_ts


def _check_audio_activity(
    ctx: ConnectionState, sid: int | None, data: bytes
) -> tuple[bool, int]:
    """判断当前帧是否为有效语音，返回 (is_active, rms)。"""
    is_active = sid is not None
    rms = 0
    try:
        rms = audioop.rms(data, 2)
        if not is_active:
            is_active = rms >= TURN_ACTIVE_AUDIO_RMS
    except audioop.error:
        is_active = False
    return is_active, rms


async def _check_asr_stall(
    ctx: ConnectionState, is_active_audio: bool, rms: int, now_ts: float
):
    """如果 ASR 持续无文本回调，尝试自动重启。"""
    source_role_now = current_source_role(ctx, now_ts)
    if not (
        is_active_audio
        and source_role_now != "candidate"
        and ctx.main_active_frames_since_text >= ASR_STALL_ACTIVE_FRAMES
        and (now_ts - ctx.last_main_asr_restart_ts)
        >= ASR_RESTART_COOLDOWN_SECONDS
    ):
        return

    since_last_text = (
        now_ts - ctx.main_last_text_ts
        if ctx.main_last_text_ts > 0
        else None
    )
    ctx.trace(
        "asr_stall_detected",
        recv_count=ctx.recv_count,
        active_frames_since_text=ctx.main_active_frames_since_text,
        since_last_text=(
            round(since_last_text, 3) if since_last_text is not None else None
        ),
        source_role=source_role_now,
        rms=rms,
        turn_id=(
            ctx.turn_manager.current_turn.get("id")
            if ctx.turn_manager.current_turn
            else None
        ),
    )
    try:
        ctx.asr_processor.stop()
    except Exception:
        pass

    from server.handlers.ws_handler import start_main_asr_with_fallback

    restarted = await start_main_asr_with_fallback(ctx, reason="stall_restart")
    ctx.main_active_frames_since_text = 0
    ctx.last_main_asr_restart_ts = now_ts
    if restarted:
        ctx.trace("asr_restarted", recv_count=ctx.recv_count)
    else:
        ctx.trace("asr_restart_failed", recv_count=ctx.recv_count)
