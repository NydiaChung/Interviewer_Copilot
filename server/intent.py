"""统一意图检测模块 — 问题识别 + 草稿生成时机判断。

暴露的公共接口：
  - is_question_like(text)          判断文本是否类似问题（供 main.py 关闭决策使用）
  - IntentReadinessDetector         判断 ASR 中间结果何时足够成熟可生成草稿 outline
"""

from __future__ import annotations

import re
import time
from difflib import SequenceMatcher


# ── 问题信号词汇 ─────────────────────────────────────────────────────────────
# 疑问句：以疑问词或句末助词结尾的句子
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
    # 疑问副词
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
    # 陈述式问题（Fix 5 新增）
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


def is_question_like(text: str) -> bool:
    """判断文本是否含问题信号词。

    供 main.py 的问题关闭决策调用，替代原有的 _is_question_like() 局部函数。
    """
    t = (text or "").strip()
    if not t:
        return False
    return any(h in t for h in QUESTION_HINTS)


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
