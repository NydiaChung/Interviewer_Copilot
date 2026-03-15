"""JSON 命令分发：end_session、manual_question、truncate、source_activity。"""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from server.config import (
    ANALYSIS_FALLBACK_TEXT,
    LLM_ANALYSIS_TIMEOUT_SECONDS,
    SOURCE_TAKEOVER_CLOSE_WINDOW_SECONDS,
)
from server.handlers.answer_scheduler import call_with_timeout, schedule_answer
from server.handlers.turn_closer import maybe_close_turn
from server.llm import llm_processor

if TYPE_CHECKING:
    from server.models.connection import ConnectionState


async def handle_command(ctx: ConnectionState, cmd_json: dict) -> bool:
    """处理 JSON 命令。返回 True 表示应跳出主循环（end_session）。"""
    command = cmd_json.get("command", "")
    cmd_type = cmd_json.get("type", "")

    if cmd_type == "audio":
        return False  # 音频帧由外层处理

    if command == "end_session":
        await _handle_end_session(ctx)
        return True

    if command == "source_activity":
        _handle_source_activity(ctx, cmd_json)
        return False

    if command == "manual_question":
        await _handle_manual_question(ctx, cmd_json)
        return False

    if command == "truncate":
        await _handle_truncate(ctx, cmd_json)
        return False

    return False


async def _handle_end_session(ctx: ConnectionState):
    """结束会话：停止 ASR、生成分析报告、保存文件。"""
    ctx.trace("command_end_session")
    print(
        f"[Memory] Session ended by user. "
        f"Generating analysis for: {ctx.session_id}"
    )

    ctx.asr_processor.stop()
    if ctx.asr_candidate:
        ctx.asr_candidate.stop()

    if ctx.close_check_task and not ctx.close_check_task.done():
        ctx.close_check_task.cancel()
    if ctx.outline_task and not ctx.outline_task.done():
        ctx.outline_task.cancel()

    turn = ctx.turn_manager.current_turn
    if turn and not turn.get("closed"):
        await maybe_close_turn(ctx, turn.get("id"), reason="session_end", force=True)

    # 等待未完成的回答任务
    pending = [t for t in ctx.answer_tasks if not t.done()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    history_text = ctx.session.format_history_for_llm()

    analysis = await call_with_timeout(
        llm_processor.generate_analysis(
            jd=ctx.session.jd_text,
            resume=ctx.session.resume_text,
            history=history_text,
        ),
        timeout_seconds=LLM_ANALYSIS_TIMEOUT_SECONDS,
        fallback_text=ANALYSIS_FALLBACK_TEXT,
    )

    # 保存文件
    with open(ctx.transcript_file_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "jd": ctx.session.jd_text,
                "resume": ctx.session.resume_text,
                "history": ctx.session.get_sorted_transcript(),
                "analysis": analysis,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    await ctx.websocket.send_json(
        {
            "type": "analysis",
            "answer": analysis,
            "trace_id": ctx.trace_id,
        }
    )


def _handle_source_activity(ctx: ConnectionState, cmd_json: dict):
    """更新音源活跃度状态。"""
    now_ts = time.monotonic()
    dominant = str(
        cmd_json.get(
            "dominant_source",
            ctx.source_activity.get("dominant_source", "unknown"),
        )
    )
    prev_dominant = str(ctx.source_activity.get("dominant_source", "unknown"))
    ctx.source_activity["dominant_source"] = dominant
    ctx.source_activity["mic_rms"] = int(cmd_json.get("mic_rms", 0) or 0)
    ctx.source_activity["system_rms"] = int(
        cmd_json.get("system_rms", 0) or 0
    )
    ctx.source_activity["ts"] = now_ts
    if dominant != prev_dominant:
        ctx.source_activity["change_ts"] = now_ts
    ctx.trace(
        "source_activity",
        dominant_source=dominant,
        mic_rms=ctx.source_activity["mic_rms"],
        system_rms=ctx.source_activity["system_rms"],
        changed=(dominant != prev_dominant),
    )


async def _handle_manual_question(ctx: ConnectionState, cmd_json: dict):
    """手动提问命令。"""
    manual_text = cmd_json.get("text", "").strip()
    if not manual_text:
        return

    ctx.trace("command_manual_question", text_preview=manual_text[:80])
    print(f"[Manual] User sent: {manual_text}")

    if ctx.close_check_task and not ctx.close_check_task.done():
        ctx.close_check_task.cancel()

    turn = ctx.turn_manager.current_turn
    if turn and not turn.get("closed"):
        await maybe_close_turn(
            ctx, turn.get("id"), reason="manual_takeover", force=True
        )

    manual_turn_id = ctx.turn_manager.next_turn_id
    ctx.turn_manager.next_turn_id += 1
    ctx.session.append_transcript(
        seq=len(ctx.session.transcript) + 1,
        source="manual",
        question_id=manual_turn_id,
        question=manual_text,
        answer="",
    )
    await ctx.websocket.send_json(
        {
            "type": "incremental",
            "text": f"🙋 {manual_text}",
            "question_id": manual_turn_id,
            "speaker_id": 999,
            "speaker_role": "interviewer",
            "trace_id": ctx.trace_id,
        }
    )
    schedule_answer(ctx, manual_text, "manual", manual_turn_id)


async def _handle_truncate(ctx: ConnectionState, cmd_json: dict):
    """手动截断当前轮次。"""
    target_qid = cmd_json.get("question_id")
    ctx.trace("command_truncate", target_qid=target_qid)

    turn = ctx.turn_manager.current_turn
    if turn and not turn.get("closed"):
        if target_qid is None or turn.get("id") == target_qid:
            print(
                f"[Manual] User triggered truncate for turn {turn.get('id')}"
            )
            await maybe_close_turn(
                ctx, turn.get("id"), reason="manual_truncate", force=True
            )
