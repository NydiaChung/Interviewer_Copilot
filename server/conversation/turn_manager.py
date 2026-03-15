"""对话轮次状态管理核心类。"""

import time
from typing import Any, Dict, Optional

from server.conversation.turn_state import TurnState


class TurnManager:
    """轮次状态机：只在音源切换（麦克风 ↔ 系统）时开新气泡。"""

    def __init__(self):
        self.current_turn: Optional[Dict[str, Any]] = None
        self.next_turn_id = 1
        self.state: TurnState = TurnState.CLOSED
        self.last_new_turn_eval: Dict[str, Any] = {}

    def is_recording(self) -> bool:
        """判断是否处于录音/草稿状态"""
        return self.state in (TurnState.RECORDING, TurnState.DRAFTING)

    def is_drafting(self) -> bool:
        """判断是否处于草稿状态"""
        return self.state == TurnState.DRAFTING

    def mark_drafting(self):
        """外部 LLM 调度器发出了草稿后，反向标记状态"""
        if self.state == TurnState.RECORDING:
            self.state = TurnState.DRAFTING

    def mark_closed(self):
        """标记当前轮次为关闭状态"""
        self.state = TurnState.CLOSED
        if self.current_turn:
            self.current_turn["closed"] = True

    def create_turn(
        self,
        text: str,
        norm_text: str,
        speaker_id: Optional[int],
        source_role: str = "interviewer",
        asr_baseline: str = "",
    ) -> Dict[str, Any]:
        """开启并进入新的一轮对话"""
        now_ts = time.monotonic()
        self.current_turn = {
            "id": self.next_turn_id,
            "text": text,
            "norm": norm_text,
            "source_role": source_role,
            "asr_baseline": asr_baseline,
            "created_ts": now_ts,
            "audio_last_ts": now_ts,
            "text_last_ts": now_ts,
            "speaker_id": speaker_id,
            "closed": False,
        }
        self.next_turn_id += 1
        self.state = TurnState.RECORDING
        return self.current_turn

    def update_turn_text(self, text: str, norm_text: str):
        """持续注入文本增量，并更新触碰时间线"""
        if not self.current_turn:
            return
        now_ts = time.monotonic()
        self.current_turn["text"] = text
        self.current_turn["norm"] = norm_text
        self.current_turn["text_last_ts"] = now_ts
        self.current_turn["audio_last_ts"] = now_ts

    def check_should_start_new_turn(
        self,
        incoming_source_role: str,
    ) -> bool:
        """判断是否应开新气泡 —— 只在音源切换时触发。

        麦克风 → candidate，系统音频 → interviewer。
        音源不变则继续当前气泡。
        """
        turn = self.current_turn
        if not turn or turn.get("closed"):
            self.last_new_turn_eval = {"trigger": False, "reason": "no_turn"}
            return False

        current_role = turn.get("source_role", "interviewer")

        if incoming_source_role == current_role:
            self.last_new_turn_eval = {
                "trigger": False,
                "reason": "same_source",
            }
            return False

        self.last_new_turn_eval = {
            "trigger": True,
            "reason": "source_switch",
            "from": current_role,
            "to": incoming_source_role,
        }
        return True
