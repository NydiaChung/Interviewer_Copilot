"""轮次状态枚举。"""

from enum import Enum


class TurnState(Enum):
    CLOSED = "closed"
    RECORDING = "recording"
    DRAFTING = "drafting"
