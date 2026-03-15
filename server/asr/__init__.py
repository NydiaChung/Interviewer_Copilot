"""ASR 模块 — 多提供商切换（豆包 / 通义听悟）。"""

import os

from server.asr.base import ASRProvider
from server.asr.doubao import DoubaoProvider
from server.asr.tingwu import TingwuProvider

_PROVIDER = os.getenv("ASR_PROVIDER", "tingwu").lower()


def get_asr_processor() -> ASRProvider:
    """根据 ASR_PROVIDER 环境变量创建对应的 ASR 实例。"""
    print(f"[ASR] 使用 {_PROVIDER} ASR 提供商")
    if _PROVIDER == "tingwu":
        return TingwuProvider()
    return DoubaoProvider()


__all__ = [
    "ASRProvider",
    "DoubaoProvider",
    "TingwuProvider",
    "get_asr_processor",
]
