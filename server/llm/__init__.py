"""LLM 模块 — 多提供商 + 自动 Fallback。"""

from server.llm.base import BaseLLMProcessor
from server.llm.fallback import get_llm_processor

# 惰性单例：首次访问时才初始化，避免无 API Key 环境下 import 就崩溃
_llm_processor = None


def _get_singleton() -> BaseLLMProcessor:
    global _llm_processor
    if _llm_processor is None:
        _llm_processor = get_llm_processor()
    return _llm_processor


class _LazyProxy:
    """属性代理，首次调用时才实例化底层 LLM 处理器。"""

    def __getattr__(self, name):
        return getattr(_get_singleton(), name)


llm_processor: BaseLLMProcessor = _LazyProxy()  # type: ignore[assignment]

__all__ = [
    "BaseLLMProcessor",
    "get_llm_processor",
    "llm_processor",
]
