"""LLM module for generating interview answers."""

import os
import asyncio
from typing import Any, Optional, Tuple, List

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


def _safe_text(value: Any) -> str:
    """Normalize model outputs to plain string for UI and transcript storage."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


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
        return _safe_text(response.choices[0].message.content)

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
        return _safe_text(response.choices[0].message.content)

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
        return _safe_text(response.choices[0].message.content)


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
            return _safe_text(response.output.choices[0].message.content)
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
            return _safe_text(response.output.choices[0].message.content)
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
            return _safe_text(response.output.choices[0].message.content)
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
        return _safe_text(response.text)

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
        return _safe_text(response.text)

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
        return _safe_text(response.text)


class FallbackLLMProcessor(BaseLLMProcessor):
    """Try multiple providers sequentially at runtime when one fails."""

    def __init__(self, providers: List[Tuple[str, BaseLLMProcessor]]):
        self.providers = providers

    async def _run(self, method_name: str, *args) -> str:
        last_exc = None
        for provider_name, processor in self.providers:
            try:
                method = getattr(processor, method_name)
                result = _safe_text(await method(*args))
                if result:
                    return result
                print(f"[LLM] {provider_name}.{method_name} returned empty, trying next.")
            except Exception as e:
                last_exc = e
                print(f"[LLM] {provider_name}.{method_name} failed: {e}")
        if last_exc:
            raise last_exc
        return ""

    async def generate_outline(self, jd: str, resume: str, question: str) -> str:
        return await self._run("generate_outline", jd, resume, question)

    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        return await self._run("generate_answer", jd, resume, question)

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        return await self._run("generate_analysis", jd, resume, history)


def _build_processor(name: str) -> Optional[Tuple[str, BaseLLMProcessor]]:
    name = (name or "").strip().lower()
    if name == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            return None
        try:
            return ("openai", OpenAIProcessor())
        except Exception as e:
            print(f"[LLM] openai init failed: {e}")
            return None
    if name == "dashscope":
        if not os.getenv("DASHSCOPE_API_KEY"):
            return None
        try:
            return ("dashscope", DashScopeProcessor())
        except Exception as e:
            print(f"[LLM] dashscope init failed: {e}")
            return None
    if name == "gemini":
        if not os.getenv("GEMINI_API_KEY"):
            return None
        try:
            return ("gemini", GeminiProcessor())
        except Exception as e:
            print(f"[LLM] gemini init failed: {e}")
            return None
    return None


def _parse_order(raw: str) -> List[str]:
    seen = set()
    order = []
    for part in (raw or "").split(","):
        name = part.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        order.append(name)
    return order


def get_llm_processor() -> BaseLLMProcessor:
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    auto_order = _parse_order(os.getenv("LLM_AUTO_ORDER", "dashscope,openai,gemini"))

    if provider in {"openai", "dashscope", "gemini"}:
        built = _build_processor(provider)
        if not built:
            raise ValueError(f"{provider} provider is not configured correctly")
        return built[1]

    # auto mode: build all available providers in order, and runtime-fallback across them
    built_providers = []
    for name in auto_order:
        built = _build_processor(name)
        if built:
            built_providers.append(built)

    if not built_providers:
        raise ValueError(
            "No available LLM provider. Please configure at least one API key."
        )
    if len(built_providers) == 1:
        provider_name, processor = built_providers[0]
        print(f"[LLM] Auto mode selected single provider: {provider_name}")
        return processor

    names = ",".join([name for name, _ in built_providers])
    print(f"[LLM] Auto mode enabled with fallback chain: {names}")
    return FallbackLLMProcessor(built_providers)


# Singleton instance
llm_processor = get_llm_processor()
