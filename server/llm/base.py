"""LLM 基类 — 模板方法模式消除各 Provider 的重复代码。"""

import asyncio
from typing import Any


def safe_text(value: Any) -> str:
    """将模型输出标准化为纯字符串。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


class BaseLLMProcessor:
    """LLM 处理器基类。

    子类只需实现 ``_call(prompt, model)`` 即可，三种生成方法
    的 prompt 组装 + 空值检查 + safe_text 包装由基类统一处理。
    """

    # 子类通过覆盖这些属性来指定默认模型
    outline_model: str = ""
    answer_model: str = ""
    analysis_model: str = ""

    async def _call(self, prompt: str, model: str) -> str:
        """子类实现：调用具体 LLM API，返回原始文本。"""
        raise NotImplementedError

    async def generate_outline(
        self, jd: str, resume: str, question: str
    ) -> str:
        if not question.strip():
            return ""
        from server.prompts import OUTLINE_PROMPT

        prompt = OUTLINE_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )
        return safe_text(await self._call(prompt, self.outline_model))

    async def generate_answer(
        self, jd: str, resume: str, question: str
    ) -> str:
        if not question.strip():
            return ""
        from server.prompts import INTERVIEW_PROMPT

        prompt = INTERVIEW_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )
        return safe_text(await self._call(prompt, self.answer_model))

    async def generate_analysis(
        self, jd: str, resume: str, history: str
    ) -> str:
        if not history.strip():
            return "本次面试没有记录下足够的对话，无法进行深入复盘。"
        from server.prompts import ANALYSIS_PROMPT

        prompt = ANALYSIS_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", history=history
        )
        return safe_text(await self._call(prompt, self.analysis_model))
