"""Outline 草稿触发时机判断器。

根据 ASR 中间结果的稳定性、问题信号强度、停顿时长等维度
评分，决定何时预生成 outline 草稿。
"""

from __future__ import annotations

import time

from server.conversation.turn_rules import QUESTION_HINTS, is_question_like
from server.utils.text import normalize_text, text_similarity

INTENT_KEYWORDS = (
    "项目",
    "经历",
    "职责",
    "挑战",
    "难点",
    "方案",
    "优化",
    "架构",
    "tradeoff",
    "取舍",
    "性能",
    "稳定",
    "故障",
    "排查",
    "冲突",
    "协作",
    "优缺点",
    "例子",
    "场景",
)


class IntentReadinessDetector:
    """决策何时 ASR 中间文本已足够稳定/清晰，可以预生成 outline 草稿。"""

    def __init__(
        self,
        min_chars: int = 6,
        min_score: int = 4,
        debounce_seconds: float = 0.6,
        pause_seconds: float = 0.45,
        stable_similarity: float = 0.86,
        dedup_similarity: float = 0.90,
    ):
        self.min_chars = min_chars
        self.min_score = min_score
        self.debounce_seconds = debounce_seconds
        self.pause_seconds = pause_seconds
        self.stable_similarity = stable_similarity
        self.dedup_similarity = dedup_similarity
        self._last_text = ""
        self._last_ts = 0.0
        self._stable_count = 0
        self._last_trigger_text = ""
        self._last_trigger_ts = -1e9

    def reset(self):
        self._last_text = ""
        self._last_ts = 0.0
        self._stable_count = 0
        self._last_trigger_text = ""
        self._last_trigger_ts = -1e9

    def _score(self, text: str, now: float) -> int:
        score = 0
        if len(text) >= self.min_chars:
            score += 1
        if len(text) >= 12:
            score += 1
        if any(token in text for token in QUESTION_HINTS):
            score += 2
        if any(token in text for token in INTENT_KEYWORDS):
            score += 2
        if text.endswith(("?", "？", "吗", "么", "呢")):
            score += 1

        if self._last_text:
            sim_prev = text_similarity(text, self._last_text)
            if sim_prev >= self.stable_similarity:
                self._stable_count += 1
            else:
                self._stable_count = 0
            if self._stable_count >= 1:
                score += 2

        if self._last_ts and (now - self._last_ts) >= self.pause_seconds:
            score += 1
        return score

    def should_trigger_outline(self, text: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        normalized = normalize_text(text)
        if not normalized or len(normalized) < self.min_chars:
            self._last_text = normalized
            self._last_ts = now
            return False

        score = self._score(normalized, now)

        is_debounced = (now - self._last_trigger_ts) >= self.debounce_seconds
        is_new_enough = (
            not self._last_trigger_text
            or text_similarity(normalized, self._last_trigger_text) < self.dedup_similarity
        )

        triggered = score >= self.min_score and is_debounced and is_new_enough
        if triggered:
            self._last_trigger_text = normalized
            self._last_trigger_ts = now

        self._last_text = normalized
        self._last_ts = now
        return triggered
