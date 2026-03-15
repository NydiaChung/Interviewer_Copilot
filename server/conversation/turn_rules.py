"""轮次切分判定规则。

每个规则函数返回 ``(result, reason)``：
- ``result=True``  → 应开新轮
- ``result=False`` → 不应开新轮
- ``result=None``  → 该规则不做决策，继续交由后续规则
"""

from typing import Optional

from server.config import (
    NEW_QUESTION_SIMILARITY_THRESHOLD,
    QUESTION_PAUSE_LONG_THRESHOLD,
    QUESTION_PAUSE_MID_THRESHOLD,
    QUESTION_PAUSE_SHORT_THRESHOLD,
    SHORT_TEXT_MIN_INCOMING,
    SHORT_TEXT_MIN_INCOMING_SWITCH,
    SHORT_TEXT_MIN_PREV,
    VOICEPRINT_SWITCH_MIN_GAP_SECONDS,
    VOICEPRINT_SWITCH_SIMILARITY_THRESHOLD,
)
from server.utils.text import text_similarity


# ── 问题信号词汇 ─────────────────────────────────────────────────────────────
QUESTION_HINTS = (
    "?",
    "？",
    "吗",
    "么",
    "呢",
    "why",
    "how",
    "what",
    "which",
    "when",
    "where",
    "介绍",
    "说说",
    "讲讲",
    "谈谈",
    "聊聊",
    "解释",
    "原因",
    "怎么",
    "如何",
    "为什么",
    "有哪些",
    "能不能",
    "可不可以",
    "请你",
    "什么",
    "哪些",
    "哪种",
    "具体",
    "经验",
    "背景",
    "过程",
    "遇到",
    "说明",
    "描述",
    "是否",
)


def is_question_like(text: str) -> bool:
    """判断文本是否含问题信号词。"""
    t = (text or "").strip()
    if not t:
        return False
    return any(h in t for h in QUESTION_HINTS)


def check_speaker_switch_rule(
    incoming_speaker: Optional[int],
    turn_speaker: Optional[int],
    incoming_norm_text: str,
    prev_norm: str,
    speech_gap: float,
) -> tuple[bool, str]:
    """规则 1：声纹切换 + 文本不相似 + 足够停顿。"""
    speaker_switched = (
        incoming_speaker is not None
        and turn_speaker is not None
        and incoming_speaker != turn_speaker
    )
    sim = text_similarity(incoming_norm_text, prev_norm)
    if (
        speaker_switched
        and sim <= VOICEPRINT_SWITCH_SIMILARITY_THRESHOLD
        and speech_gap >= VOICEPRINT_SWITCH_MIN_GAP_SECONDS
    ):
        return True, "speaker_switch_gap"
    return False, ""


def check_low_similarity_question_rule(
    incoming_norm_text: str,
    prev_norm: str,
    speech_gap: float,
) -> tuple[bool, str]:
    """规则 2：低相似 + 提问特征 + 足够停顿。"""
    sim = text_similarity(incoming_norm_text, prev_norm)
    if (
        sim < NEW_QUESTION_SIMILARITY_THRESHOLD
        and incoming_norm_text not in prev_norm
        and prev_norm not in incoming_norm_text
        and (is_question_like(incoming_norm_text) or is_question_like(prev_norm))
        and speech_gap >= QUESTION_PAUSE_SHORT_THRESHOLD
    ):
        return True, "low_similarity_question_like"
    return False, ""


def check_similar_text_continue_rule(
    incoming_speaker: Optional[int],
    turn_speaker: Optional[int],
    incoming_norm_text: str,
    prev_norm: str,
) -> tuple[bool, str]:
    """规则 3：高相似且未切换声纹 → 禁止切分。"""
    sim = text_similarity(incoming_norm_text, prev_norm)
    if sim >= NEW_QUESTION_SIMILARITY_THRESHOLD:
        return True, "similar_text_continue"
    return False, ""


def check_asr_final_rule(
    asr_got_final: bool,
    incoming_speaker: Optional[int],
    turn_speaker: Optional[int],
    turn_text: str,
    speech_gap: float,
) -> tuple[Optional[bool], str]:
    """规则 4：ASR 终结信号判断。"""
    if not asr_got_final:
        return None, ""

    speaker_switched = (
        incoming_speaker is not None
        and turn_speaker is not None
        and incoming_speaker != turn_speaker
    )
    if speaker_switched:
        return True, "got_final_speaker_switched"
    if is_question_like(turn_text) and speech_gap >= QUESTION_PAUSE_MID_THRESHOLD:
        return True, "got_final_question_like_pause"
    return False, "got_final_wait_more_signal"


def check_question_pause_rule(
    turn_text: str, speech_gap: float
) -> tuple[bool, str]:
    """规则 5：提问特征 + 长停顿。"""
    if is_question_like(turn_text) and speech_gap >= QUESTION_PAUSE_LONG_THRESHOLD:
        return True, "question_like_pause"
    return False, ""


def check_short_text_rule(
    prev_norm: str,
    incoming_norm_text: str,
    incoming_speaker: Optional[int],
    turn_speaker: Optional[int],
    asr_got_final: bool,
    speech_gap: float,
) -> tuple[Optional[bool], str]:
    """短文本特殊规则。"""
    if (
        len(prev_norm) >= SHORT_TEXT_MIN_PREV
        and len(incoming_norm_text) >= SHORT_TEXT_MIN_INCOMING
    ):
        return None, ""

    speaker_switched = (
        incoming_speaker is not None
        and turn_speaker is not None
        and incoming_speaker != turn_speaker
    )
    if (
        speaker_switched
        and asr_got_final
        and len(incoming_norm_text) >= SHORT_TEXT_MIN_INCOMING_SWITCH
    ):
        return True, "short_text_speaker_switched"

    if is_question_like(prev_norm) and speech_gap >= QUESTION_PAUSE_LONG_THRESHOLD:
        return None, ""

    return False, "short_text_not_ready"
