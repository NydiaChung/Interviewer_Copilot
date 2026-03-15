"""轮次关闭逻辑：_maybe_close_turn + _arm_close_check。"""

from __future__ import annotations

import asyncio
import time
from difflib import SequenceMatcher
from typing import TYPE_CHECKING

from server.config import (
    CLOSE_WATCHER_POLL_SECONDS,
    VOICEPRINT_CLOSE_SILENCE_SECONDS,
    SOURCE_TAKEOVER_CLOSE_WINDOW_SECONDS,
)
from server.conversation.turn_rules import is_question_like

if TYPE_CHECKING:
    from server.models.connection import ConnectionState


async def maybe_close_turn(
    ctx: ConnectionState,
    turn_id: int,
    reason: str,
    force: bool = False,
) -> bool:
    """尝试关闭指定轮次。返回 True 表示已关闭。"""
    from server.handlers.answer_scheduler import schedule_answer
    from server.handlers.audio_processor import current_source_role

    turn = ctx.turn_manager.current_turn
    if not turn or turn.get("id") != turn_id or turn.get("closed"):
        return False

    now_ts = time.monotonic()
    silence = now_ts - turn.get("audio_last_ts", now_ts)
    source_role = current_source_role(ctx, now_ts)

    # 声纹换人字段
    dominant_speaker = ctx.last_dominant_speaker
    speaker_switched = (
        dominant_speaker is not None
        and turn.get("speaker_id") is not None
        and dominant_speaker != turn.get("speaker_id")
    )

    # 声纹增强关闭
    voiceprint_close = (
        speaker_switched
        and len(turn.get("norm", "")) >= 10
        and silence >= VOICEPRINT_CLOSE_SILENCE_SECONDS
        and (now_ts - ctx.last_speaker_change_ts) <= 2.0
    )

    # 音源接管关闭
    source_takeover_close = (
        source_role == "candidate"
        and len(turn.get("norm", "")) >= 8
        and (
            now_ts
            - float(ctx.source_activity.get("change_ts", 0.0) or 0.0)
        )
        <= SOURCE_TAKEOVER_CLOSE_WINDOW_SECONDS
    )

    should_close = (
        force
        or voiceprint_close
        or source_takeover_close
        or silence >= 5.0
    )

    is_q_like = is_question_like(turn.get("text", ""))
    got_final_flag = turn.get("got_final", False)

    close_eval = {
        "turn_id": turn_id,
        "reason": reason,
        "force": bool(force),
        "silence": round(silence, 3),
        "got_final": bool(got_final_flag),
        "is_question_like": bool(is_q_like),
        "voiceprint_close": bool(voiceprint_close),
        "source_takeover_close": bool(source_takeover_close),
        "source_role": source_role,
        "speaker_switched": bool(speaker_switched),
        "dominant_speaker": dominant_speaker,
    }

    if not should_close:
        if reason != "silence":
            ctx.trace("turn_close_skipped", **close_eval)
        else:
            turn["close_check_count"] = int(
                turn.get("close_check_count", 0)
            ) + 1
            if turn["close_check_count"] % 8 == 1:
                ctx.trace("turn_close_poll", **close_eval)
        return False

    close_log = (
        f"reason={reason}  silence={silence:.2f}s  "
        f"got_final={got_final_flag}  "
        f"voiceprint_close={voiceprint_close}  "
        f"source_takeover_close={source_takeover_close}  "
        f"speaker_switched={speaker_switched}  "
        f"dominant_speaker={dominant_speaker}"
    )
    print(f"[Turn] 关闭 turn={turn_id}  {close_log}")
    ctx.trace("turn_closed", **close_eval)

    ctx.turn_manager.mark_closed()
    turn["close_reason"] = reason
    ctx.intent_detector.reset()

    if ctx.outline_task and not ctx.outline_task.done():
        ctx.outline_task.cancel()

    # 去重判断
    normalized = turn.get("norm", "")
    if (
        normalized
        and SequenceMatcher(
            None, normalized, ctx.last_answer_trigger_text
        ).ratio()
        >= 0.97
        and (now_ts - ctx.last_answer_trigger_ts) <= 8
    ):
        print(f"[LLM] 跳过重复问题触发: {turn.get('text', '')}")
        ctx.trace(
            "turn_answer_skipped_duplicate",
            turn_id=turn_id,
            normalized=normalized[:80],
        )
        return True

    ctx.last_answer_trigger_text = normalized
    ctx.last_answer_trigger_ts = now_ts
    schedule_answer(
        ctx,
        turn.get("text", ""),
        source="asr",
        question_id=turn.get("id"),
    )
    return True


def arm_close_check(ctx: ConnectionState, turn_id: int):
    """启动轮询协程监控轮次关闭条件 + 草稿触发。"""
    from server.handlers.answer_scheduler import schedule_answer

    if ctx.close_check_task and not ctx.close_check_task.done():
        ctx.close_check_task.cancel()

    async def _watcher():
        try:
            last_draft_text_len = 0
            while True:
                await asyncio.sleep(CLOSE_WATCHER_POLL_SECONDS)
                turn = ctx.turn_manager.current_turn
                if not turn or turn.get("id") != turn_id:
                    break
                if turn.get("closed"):
                    break

                closed = await maybe_close_turn(
                    ctx, turn_id, reason="silence"
                )
                if closed:
                    break

                # 草稿逻辑
                now_ts = time.monotonic()
                silence = now_ts - turn.get("audio_last_ts", now_ts)
                curr_norm = turn.get("norm", "")
                curr_text_len = len(curr_norm)

                speaker = turn.get("speaker_id")
                role = (
                    ctx.speaker_mapping_state.get(speaker, "unknown")
                    if speaker is not None
                    else "interviewer"
                )

                if (
                    role == "interviewer"
                    and silence >= 1.5
                    and (curr_text_len - last_draft_text_len) >= 5
                ):
                    last_draft_text_len = curr_text_len
                    ctx.turn_manager.mark_drafting()
                    schedule_answer(
                        ctx,
                        turn.get("text", ""),
                        source="asr_draft",
                        question_id=turn_id,
                        is_draft=True,
                    )
        except asyncio.CancelledError:
            return

    ctx.close_check_task = asyncio.create_task(_watcher())
    ctx.background_tasks.add(ctx.close_check_task)
    ctx.close_check_task.add_done_callback(ctx.background_tasks.discard)
