"""LLM module for generating interview answers."""

import os
import asyncio

try:
    from server.prompt import INTERVIEW_PROMPT, OUTLINE_PROMPT, ANALYSIS_PROMPT
except ModuleNotFoundError:
    # Fallback for running from server/ directory directly.
    from prompt import INTERVIEW_PROMPT, OUTLINE_PROMPT, ANALYSIS_PROMPT


class BaseLLMProcessor:
    async def generate_outline(self, jd: str, resume: str, question: str) -> str:
        raise NotImplementedError

    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        raise NotImplementedError

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        raise NotImplementedError


class OpenAIProcessor(BaseLLMProcessor):
    def __init__(self):
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)

    async def generate_outline(self, jd: str, resume: str, question: str) -> str:
        if not question.strip():
            return ""

        prompt = OUTLINE_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=50,
        )
        return response.choices[0].message.content.strip()

    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        if not question.strip():
            return ""

        prompt = INTERVIEW_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )
        return response.choices[0].message.content.strip()

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        if not history.strip():
            return "本次面试没有记录下足够的对话，无法进行深入复盘。"

        prompt = ANALYSIS_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", history=history
        )

        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model="gpt-4o",  # Use a stronger model for analysis
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500,
        )
        return response.choices[0].message.content.strip()


class DashScopeProcessor(BaseLLMProcessor):
    def __init__(self):
        import dashscope

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        dashscope.api_key = api_key

    async def generate_outline(self, jd: str, resume: str, question: str) -> str:
        import dashscope

        if not question.strip():
            return ""

        prompt = OUTLINE_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )

        response = await asyncio.to_thread(
            dashscope.Generation.call,
            model=dashscope.Generation.Models.qwen_plus,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.7,
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content.strip()
        else:
            print(f"[LLM] DashScope error: {response.code} - {response.message}")
            return ""

    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        import dashscope

        if not question.strip():
            return ""

        prompt = INTERVIEW_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )

        response = await asyncio.to_thread(
            dashscope.Generation.call,
            model=dashscope.Generation.Models.qwen_plus,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.7,
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content.strip()
        else:
            print(f"[LLM] DashScope error: {response.code} - {response.message}")
            return ""

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        import dashscope

        if not history.strip():
            return "本次面试没有记录下足够的对话，无法进行深入复盘。"

        prompt = ANALYSIS_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", history=history
        )

        response = await asyncio.to_thread(
            dashscope.Generation.call,
            model=dashscope.Generation.Models.qwen_max,  # Prefer max for deep analysis
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.7,
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content.strip()
        else:
            print(f"[LLM] DashScope error: {response.code} - {response.message}")
            return "分析生成失败。"


class GeminiProcessor(BaseLLMProcessor):
    def __init__(self):
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        self.client = genai.Client(api_key=api_key)

    async def generate_outline(self, jd: str, resume: str, question: str) -> str:
        if not question.strip():
            return ""

        prompt = OUTLINE_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        if not question.strip():
            return ""

        prompt = INTERVIEW_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", question=question
        )

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        if not history.strip():
            return "本次面试没有记录下足够的对话，无法进行深入复盘。"

        prompt = ANALYSIS_PROMPT.format(
            jd=jd or "未提供", resume=resume or "未提供", history=history
        )

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model="gemini-2.5-pro",  # Pro for deeper reasoning
            contents=prompt,
        )
        return response.text.strip()


def get_llm_processor() -> BaseLLMProcessor:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "dashscope":
        return DashScopeProcessor()
    elif provider == "gemini":
        return GeminiProcessor()
    else:
        return OpenAIProcessor()


# Singleton instance
llm_processor = get_llm_processor()
