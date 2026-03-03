"""Heuristic intent readiness detector for early outline generation."""

from __future__ import annotations

import re
import time
from difflib import SequenceMatcher


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
    "解释",
    "原因",
    "怎么",
    "如何",
    "为什么",
    "有哪些",
    "能不能",
    "可不可以",
    "请你",
)

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


def _normalize(text: str) -> str:
    text = (text or "").strip().lower()
    return re.sub(r"\s+", " ", text)


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


class IntentReadinessDetector:
    """Decide when partial ASR text is stable/clear enough for draft outline."""

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
            sim_prev = _similarity(text, self._last_text)
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
        normalized = _normalize(text)
        if not normalized or len(normalized) < self.min_chars:
            self._last_text = normalized
            self._last_ts = now
            return False

        score = self._score(normalized, now)

        is_debounced = (now - self._last_trigger_ts) >= self.debounce_seconds
        is_new_enough = (
            not self._last_trigger_text
            or _similarity(normalized, self._last_trigger_text) < self.dedup_similarity
        )

        triggered = score >= self.min_score and is_debounced and is_new_enough
        if triggered:
            self._last_trigger_text = normalized
            self._last_trigger_ts = now

        self._last_text = normalized
        self._last_ts = now
        return triggered
