"""LLM 回答 / Outline 调度 + 流式推送。"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from server.config import (
    ANSWER_FALLBACK_TEXT,
    ANSWER_STREAM_INTERVAL_SECONDS,
    LLM_ANSWER_TIMEOUT_SECONDS,
    LLM_OUTLINE_TIMEOUT_SECONDS,
)
from server.llm import llm_processor
from server.utils.text import chunk_answer_text

if TYPE_CHECKING:
    from server.models.connection import ConnectionState


async def call_with_timeout(
    coro, timeout_seconds: int, fallback_text: str
) -> str:
    """带超时的协程调用，失败返回 fallback。"""
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


async def stream_answer_to_client(
    ctx: ConnectionState,
    seq: int,
    question_snapshot: str,
    answer_text: str,
    question_id,
):
    """分片流式推送回答到前端。"""
    chunks = chunk_answer_text(answer_text)
    if not chunks:
        chunks = [answer_text]

    if len(chunks) == 1:
        await ctx.websocket.send_json(
            {
                "type": "answer",
                "question": question_snapshot,
                "answer": answer_text,
                "seq": seq,
                "question_id": question_id,
                "streaming": False,
                "trace_id": ctx.trace_id,
            }
        )
        return

    partial = ""
    for chunk in chunks:
        partial += chunk
        await ctx.websocket.send_json(
            {
                "type": "answer",
                "question": question_snapshot,
                "answer": partial,
                "seq": seq,
                "question_id": question_id,
                "streaming": True,
                "trace_id": ctx.trace_id,
            }
        )
        await asyncio.sleep(ANSWER_STREAM_INTERVAL_SECONDS)

    await ctx.websocket.send_json(
        {
            "type": "answer",
            "question": question_snapshot,
            "answer": answer_text,
            "seq": seq,
            "question_id": question_id,
            "streaming": False,
            "trace_id": ctx.trace_id,
        }
    )


def schedule_answer(
    ctx: ConnectionState,
    question_text: str,
    source: str,
    question_id=None,
    is_draft: bool = False,
):
    """创建后台任务生成并推送回答。"""
    answer_seq = ctx.next_answer_seq
    ctx.next_answer_seq += 1
    ctx.trace(
        "answer_scheduled",
        seq=answer_seq,
        source=source,
        question_id=question_id,
        question_preview=(question_text or "")[:80],
        is_draft=is_draft,
    )

    async def _do_answer(
        seq: int,
        question_snapshot: str,
        source_snapshot: str,
        qid,
        draft_flag: bool,
    ):
        try:
            ctx.trace(
                "answer_generation_start",
                seq=seq,
                source=source_snapshot,
                question_id=qid,
                is_draft=draft_flag,
            )
            async with ctx.answer_generation_lock:
                answer = await call_with_timeout(
                    llm_processor.generate_answer(
                        jd=ctx.session.jd_text,
                        resume=ctx.session.resume_text,
                        question=question_snapshot,
                    ),
                    timeout_seconds=LLM_ANSWER_TIMEOUT_SECONDS,
                    fallback_text=ANSWER_FALLBACK_TEXT,
                )

            display_answer = (
                f"【草稿正在生成】{answer}" if draft_flag else answer
            )
            print(
                f"[LLM] Answer(seq={seq}, draft={draft_flag}): "
                f"{display_answer}"
            )
            ctx.trace(
                "answer_generation_done",
                seq=seq,
                source=source_snapshot,
                question_id=qid,
                answer_len=len(display_answer or ""),
                is_draft=draft_flag,
            )
            if not draft_flag:
                ctx.session.append_transcript(
                    seq=seq,
                    source=source_snapshot,
                    question_id=qid,
                    question=question_snapshot,
                    answer=display_answer,
                )
            await stream_answer_to_client(
                ctx, seq, question_snapshot, display_answer, qid
            )
        except asyncio.CancelledError:
            return
        except Exception as e:
            print(f"[LLM] 生成回答任务异常: {e}")

    task = asyncio.create_task(
        _do_answer(answer_seq, question_text, source, question_id, is_draft)
    )
    ctx.answer_tasks.add(task)
    ctx.background_tasks.add(task)
    task.add_done_callback(ctx.answer_tasks.discard)
    task.add_done_callback(ctx.background_tasks.discard)


async def generate_outline(
    ctx: ConnectionState,
    question_snapshot: str,
    outline_seq: int,
    question_id: int,
):
    """生成 outline 草稿并推送。"""
    try:
        outline = await call_with_timeout(
            llm_processor.generate_outline(
                jd=ctx.session.jd_text,
                resume=ctx.session.resume_text,
                question=question_snapshot,
            ),
            timeout_seconds=LLM_OUTLINE_TIMEOUT_SECONDS,
            fallback_text="",
        )
    except asyncio.CancelledError:
        return
    if not outline:
        return

    turn = ctx.turn_manager.current_turn
    if not turn or turn.get("id") != question_id or turn.get("closed"):
        return

    draft_text = f"【要点草稿】\n{outline}"
    try:
        await ctx.websocket.send_json(
            {
                "type": "outline",
                "question": question_snapshot,
                "answer": draft_text,
                "seq": outline_seq,
                "question_id": question_id,
                "trace_id": ctx.trace_id,
            }
        )
    except Exception as e:
        print(f"[WS] Error sending outline: {e}")
