"""Fallback LLM 处理器 + 工厂函数。"""

import os
from typing import Optional

from server.llm.base import BaseLLMProcessor, safe_text


class FallbackLLMProcessor(BaseLLMProcessor):
    """运行时依次尝试多个 Provider，任一成功即返回。"""

    def __init__(self, providers: list[tuple[str, BaseLLMProcessor]]):
        self.providers = providers

    async def _call(self, prompt: str, model: str) -> str:
        raise NotImplementedError("FallbackLLMProcessor 不直接调用 _call")

    async def _run(self, method_name: str, *args) -> str:
        last_exc = None
        for provider_name, processor in self.providers:
            try:
                method = getattr(processor, method_name)
                result = safe_text(await method(*args))
                if result:
                    return result
                print(
                    f"[LLM] {provider_name}.{method_name} 返回空，尝试下一个。"
                )
            except Exception as e:
                last_exc = e
                print(f"[LLM] {provider_name}.{method_name} 失败: {e}")
        if last_exc:
            raise last_exc
        return ""

    async def generate_outline(
        self, jd: str, resume: str, question: str
    ) -> str:
        return await self._run("generate_outline", jd, resume, question)

    async def generate_answer(
        self, jd: str, resume: str, question: str
    ) -> str:
        return await self._run("generate_answer", jd, resume, question)

    async def generate_analysis(
        self, jd: str, resume: str, history: str
    ) -> str:
        return await self._run("generate_analysis", jd, resume, history)


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------

def _build_processor(
    name: str,
) -> Optional[tuple[str, BaseLLMProcessor]]:
    name = (name or "").strip().lower()
    builder_map = {
        "openai": ("OPENAI_API_KEY", "server.llm.openai_provider", "OpenAIProcessor"),
        "dashscope": ("DASHSCOPE_API_KEY", "server.llm.dashscope_provider", "DashScopeProcessor"),
        "gemini": ("GEMINI_API_KEY", "server.llm.gemini_provider", "GeminiProcessor"),
    }
    entry = builder_map.get(name)
    if not entry:
        return None
    env_key, module_path, class_name = entry
    if not os.getenv(env_key):
        return None
    try:
        import importlib

        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return (name, cls())
    except Exception as e:
        print(f"[LLM] {name} 初始化失败: {e}")
        return None


def _parse_order(raw: str) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    for part in (raw or "").split(","):
        name = part.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        order.append(name)
    return order


def get_llm_processor() -> BaseLLMProcessor:
    """根据环境变量构建 LLM 处理器（支持 auto 模式自动 fallback）。"""
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    auto_order = _parse_order(
        os.getenv("LLM_AUTO_ORDER", "dashscope,openai,gemini")
    )

    if provider in {"openai", "dashscope", "gemini"}:
        built = _build_processor(provider)
        if not built:
            raise ValueError(
                f"{provider} provider is not configured correctly"
            )
        return built[1]

    built_providers = []
    for name in auto_order:
        built = _build_processor(name)
        if built:
            built_providers.append(built)

    if not built_providers:
        raise ValueError(
            "No available LLM provider. "
            "Please configure at least one API key."
        )
    if len(built_providers) == 1:
        provider_name, processor = built_providers[0]
        print(f"[LLM] Auto mode selected single provider: {provider_name}")
        return processor

    names = ",".join([name for name, _ in built_providers])
    print(f"[LLM] Auto mode enabled with fallback chain: {names}")
    return FallbackLLMProcessor(built_providers)
