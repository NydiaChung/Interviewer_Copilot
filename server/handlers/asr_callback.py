"""ASR 回调处理：on_text_update / on_candidate_text_update。"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from server.config import USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION
from server.conversation.turn_rules import is_question_like
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

        # 说话人识别
        incoming_speaker = getattr(ctx.asr_processor, "last_speaker_id", None)
        speaker_name = getattr(ctx.asr_processor, "last_speaker_name", None)

        if USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION:
            dominant = ctx.source_activity.get("dominant_source", "unknown")
            if dominant == "system":
                speaker_name = "interviewer"
                incoming_speaker = "sys_0"
            elif dominant == "mic":
                speaker_name = "candidate"
                incoming_speaker = "mic_1"

        if speaker_name in ("interviewer", "candidate"):
            ctx.speaker_mapping_state[incoming_speaker] = speaker_name
            source_role = speaker_name
        else:
            source_role = ctx.speaker_mapping_state.get(
                incoming_speaker, "interviewer"
            )

        current_turn = ctx.turn_manager.current_turn

        ctx.trace(
            "asr_text_update",
            current_turn_id=(
                current_turn.get("id") if current_turn else None
            ),
            is_sentence_end=bool(is_sentence_end),
            speaker_id=incoming_speaker,
            source_role=source_role,
            text_preview=text[:80],
            text_len=len(normalized),
        )

        # 候选人说话 → 只做字幕展示
        if source_role == "candidate":
            await _handle_candidate_speech(
                ctx, text, current_turn, incoming_speaker, now_ts, is_sentence_end
            )
            return

        # 面试官说话 → 轮次管理
        from server.handlers.turn_closer import maybe_close_turn, arm_close_check
        from server.handlers.answer_scheduler import generate_outline

        if current_turn and ctx.turn_manager.check_should_start_new_turn(
            normalized,
            incoming_speaker,
            source_role,
            asr_got_final=is_sentence_end,
        ):
            ctx.trace(
                "new_turn_detected",
                prev_turn_id=current_turn.get("id"),
                **ctx.turn_manager.last_new_turn_eval,
            )
            await maybe_close_turn(
                ctx,
                current_turn.get("id"),
                reason="next_question_start",
                force=True,
            )
            current_turn = None
        elif current_turn:
            ctx.trace(
                "new_turn_not_detected",
                prev_turn_id=current_turn.get("id"),
                **ctx.turn_manager.last_new_turn_eval,
            )

        # 创建或更新 turn
        if not current_turn:
            current_turn = ctx.turn_manager.create_turn(
                text, normalized, incoming_speaker,
                asr_baseline=ctx.asr_global_text,
            )
            ctx.trace(
                "turn_created",
                turn_id=current_turn.get("id"),
                speaker_id=current_turn.get("speaker_id"),
                text_preview=text[:80],
            )
        else:
            baseline = current_turn.get("asr_baseline", "")
            increment_text = _extract_increment(text, baseline)
            increment_norm = normalize_text(increment_text)
            ctx.turn_manager.update_turn_text(increment_text, increment_norm)
            if (
                current_turn.get("speaker_id") is None
                and incoming_speaker is not None
            ):
                current_turn["speaker_id"] = incoming_speaker

        # 归一化增量文本
        baseline_now = current_turn.get("asr_baseline", "")
        inc_text_now = _extract_increment(text, baseline_now)
        normalized = normalize_text(inc_text_now) or normalized

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
            ctx.trace(
                "ws_incremental_sent",
                stream="main",
                speaker_role=source_role,
                question_id=current_turn.get("id"),
                text_preview=(current_turn.get("text", "") or text)[:80],
            )
        except Exception:
            pass

        # 句末处理
        if is_sentence_end:
            current_turn["got_final"] = True
            ctx.trace(
                "asr_sentence_end",
                turn_id=current_turn.get("id"),
                text_preview=(current_turn.get("text", "") or text)[:80],
            )
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
            print("[LLM] Intent ready. Generating draft outline...")
            ctx.turn_manager.mark_drafting()
            turn_id = current_turn.get("id")
            outline_seq = ctx.next_answer_seq
            ctx.trace(
                "outline_triggered",
                turn_id=turn_id,
                seq=outline_seq,
                text_preview=text[:80],
            )

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
    now_ts: float,
    is_sentence_end: bool,
):
    """候选人发言：字幕展示 + 可能触发关闭当前面试官轮次。"""
    from server.handlers.turn_closer import maybe_close_turn

    candidate_text = text
    if current_turn:
        baseline = current_turn.get("asr_baseline", "")
        candidate_text = _extract_increment(text, baseline) or text

    try:
        await ctx.websocket.send_json(
            {
                "type": "incremental",
                "text": candidate_text,
                "question_id": (
                    current_turn.get("id") if current_turn else None
                ),
                "speaker_id": incoming_speaker,
                "speaker_role": "candidate",
                "trace_id": ctx.trace_id,
            }
        )
        ctx.trace(
            "ws_incremental_sent",
            stream="main",
            speaker_role="candidate",
            question_id=(
                current_turn.get("id") if current_turn else None
            ),
            text_preview=(candidate_text or text)[:80],
        )
    except Exception:
        pass

    if current_turn and not current_turn.get("closed"):
        force_close = bool(
            current_turn.get("got_final")
            or is_question_like(current_turn.get("text", ""))
            or (now_ts - current_turn.get("text_last_ts", now_ts) > 0.8)
        )
        await maybe_close_turn(
            ctx,
            current_turn.get("id"),
            reason="candidate_takeover",
            force=force_close,
        )


def build_candidate_callback(ctx: ConnectionState):
    """构造候选人专用 ASR 回调闭包。"""

    async def on_candidate_text_update(text: str, is_sentence_end: bool):
        if not text:
            return

        print(
            f"[Callback-Candidate] Received: {text} "
            f"(is_end={is_sentence_end})"
        )

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
        ctx.trace(
            "ws_incremental_sent",
            stream="candidate",
            speaker_role="candidate",
            question_id=-1,
            text_preview=text[:80],
        )

        if is_sentence_end:
            print(f"[Candidate-ASR] Final: {text}")
            ctx.session_transcript.append(
                {
                    "seq": len(ctx.session_transcript) + 1,
                    "source": "candidate_channel",
                    "question_id": -1,
                    "面试官的问题": "",
                    "AI参考回答": "",
                    "候选人回答": text,
                }
            )

    return on_candidate_text_update
