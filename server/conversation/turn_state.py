"""会话轮次生命周期状态枚举"""

from enum import Enum


class TurnState(Enum):
    """当前会话轮次生命周期状态"""

    RECORDING = "recording"  # 正在持续记录音频/文本
    DRAFTING = "drafting"  # 已下发草稿，但允许追加
    CLOSED = "closed"  # 此轮已终结，等待 LLM 最终答案
