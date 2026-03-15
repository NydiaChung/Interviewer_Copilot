"""ASR 回调处理：on_text_update / on_candidate_text_update。"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from server.config import USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION
from server.utils.text import normalize_text

if TYPE_CHECKING:
    from server.models.connection import ConnectionState


def _extract_increment(full_text: str, baseline: str) -> str:
    """从 ASR 全局累积文本中提取本轮新增内容。"""
    bl = baseline.strip()
    ft = full_text.strip()
    if not bl:
        return ft
    if ft.startswith(bl):
        inc = ft[len(bl):].strip()
        return inc if inc else ft
    parts = [s.strip() for s in ft.replace("，", "。").split("。") if s.strip()]
    return parts[-1] if parts else ft


def _resolve_source_role(ctx: ConnectionState, incoming_speaker) -> str:
    """根据音源确定说话人角色：系统音频=interviewer，麦克风=candidate。"""
    if USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION:
        dominant = ctx.source_activity.get("dominant_source", "unknown")
        if dominant == "system":
            return "interviewer"
        if dominant == "mic":
            return "candidate"

    # 回退：ASR 自带的说话人名
    speaker_name = getattr(ctx.asr_processor, "last_speaker_name", None)
    if speaker_name in ("interviewer", "candidate"):
        return speaker_name

    return ctx.speaker_mapping_state.get(incoming_speaker, "interviewer")


def build_text_callback(ctx: ConnectionState):
    """构造主 ASR 回调闭包。"""

    async def on_text_update(text: str, is_sentence_end: bool):
        if not text:
            return

        print(f"[Callback-Main] Received: {text} (is_end={is_sentence_end})")

        ctx.asr_global_text = text
        now_ts = time.monotonic()
        ctx.main_last_text_ts = now_ts
        ctx.main_active_frames_since_text = 0
        normalized = normalize_text(text)

        incoming_speaker = getattr(ctx.asr_processor, "last_speaker_id", None)
        source_role = _resolve_source_role(ctx, incoming_speaker)

        current_turn = ctx.turn_manager.current_turn

        ctx.trace(
            "asr_text_update",
            current_turn_id=(
                current_turn.get("id") if current_turn else None
            ),
            is_sentence_end=bool(is_sentence_end),
            source_role=source_role,
            text_preview=text[:80],
        )

        # 判断是否需要开新气泡（音源切换）
        from server.handlers.turn_closer import maybe_close_turn, arm_close_check
        from server.handlers.answer_scheduler import generate_outline

        if current_turn and ctx.turn_manager.check_should_start_new_turn(
            source_role
        ):
            ctx.trace(
                "new_turn_detected",
                prev_turn_id=current_turn.get("id"),
                **ctx.turn_manager.last_new_turn_eval,
            )
            await maybe_close_turn(
                ctx,
                current_turn.get("id"),
                reason="source_switch",
                force=True,
            )
            current_turn = None

        # 候选人说话 → 只做字幕，不触发 LLM
        if source_role == "candidate":
            await _handle_candidate_speech(
                ctx, text, current_turn, incoming_speaker,
                source_role, now_ts, is_sentence_end,
            )
            return

        # 面试官说话 → 轮次管理 + LLM
        if not current_turn:
            current_turn = ctx.turn_manager.create_turn(
                text, normalized, incoming_speaker,
                source_role=source_role,
                asr_baseline=ctx.asr_global_text,
            )
            ctx.trace(
                "turn_created",
                turn_id=current_turn.get("id"),
                source_role=source_role,
                text_preview=text[:80],
            )
        else:
            baseline = current_turn.get("asr_baseline", "")
            increment_text = _extract_increment(text, baseline)
            increment_norm = normalize_text(increment_text)
            ctx.turn_manager.update_turn_text(increment_text, increment_norm)

        # 发送增量到前端
        try:
            await ctx.websocket.send_json(
                {
                    "type": "incremental",
                    "text": current_turn.get("text", "") or text,
                    "question_id": current_turn.get("id"),
                    "speaker_id": incoming_speaker,
                    "speaker_role": source_role,
                    "trace_id": ctx.trace_id,
                }
            )
        except Exception:
            pass

        # 句末处理
        if is_sentence_end:
            current_turn["got_final"] = True
            await maybe_close_turn(
                ctx,
                current_turn.get("id"),
                reason="asr_final",
                force=False,
            )
            return

        # Outline 草稿触发
        if (
            not ctx.turn_manager.is_drafting()
            and not is_sentence_end
            and ctx.intent_detector.should_trigger_outline(text)
        ):
            ctx.turn_manager.mark_drafting()
            turn_id = current_turn.get("id")
            outline_seq = ctx.next_answer_seq

            if ctx.outline_task and not ctx.outline_task.done():
                ctx.outline_task.cancel()

            ctx.outline_task = asyncio.create_task(
                generate_outline(ctx, text, outline_seq, turn_id)
            )
            ctx.background_tasks.add(ctx.outline_task)
            ctx.outline_task.add_done_callback(ctx.background_tasks.discard)

        arm_close_check(ctx, current_turn.get("id"))

    return on_text_update


async def _handle_candidate_speech(
    ctx: ConnectionState,
    text: str,
    current_turn: dict | None,
    incoming_speaker,
    source_role: str,
    now_ts: float,
    is_sentence_end: bool,
):
    """候选人发言：创建/更新候选人气泡，不触发 LLM。"""
    normalized = normalize_text(text)

    # 没有当前轮或当前轮不是候选人 → 创建新的候选人气泡
    if not current_turn:
        current_turn = ctx.turn_manager.create_turn(
            text, normalized, incoming_speaker,
            source_role=source_role,
            asr_baseline=ctx.asr_global_text,
        )
    else:
        baseline = current_turn.get("asr_baseline", "")
        increment_text = _extract_increment(text, baseline)
        increment_norm = normalize_text(increment_text)
        ctx.turn_manager.update_turn_text(increment_text, increment_norm)

    try:
        await ctx.websocket.send_json(
            {
                "type": "incremental",
                "text": current_turn.get("text", "") or text,
                "question_id": current_turn.get("id"),
                "speaker_id": incoming_speaker,
                "speaker_role": "candidate",
                "trace_id": ctx.trace_id,
            }
        )
    except Exception:
        pass

    # 候选人句末 → 记录到 transcript
    if is_sentence_end:
        ctx.session_transcript.append(
            {
                "seq": len(ctx.session_transcript) + 1,
                "source": "candidate",
                "question_id": current_turn.get("id"),
                "候选人回答": current_turn.get("text", "") or text,
            }
        )


def build_candidate_callback(ctx: ConnectionState):
    """构造候选人专用 ASR 回调闭包（双通道模式）。"""

    async def on_candidate_text_update(text: str, is_sentence_end: bool):
        if not text:
            return

        print(f"[Callback-Candidate] Received: {text} (is_end={is_sentence_end})")

        await ctx.websocket.send_json(
            {
                "type": "incremental",
                "text": text,
                "question_id": -1,
                "speaker_id": None,
                "speaker_role": "candidate",
                "trace_id": f"{ctx.trace_id}-cand",
            }
        )

        if is_sentence_end:
            ctx.session_transcript.append(
                {
                    "seq": len(ctx.session_transcript) + 1,
                    "source": "candidate_channel",
                    "question_id": -1,
                    "候选人回答": text,
                }
            )

    return on_candidate_text_update
