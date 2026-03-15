"""对话轮次状态管理核心类。"""

import time
from typing import Any, Dict, Optional

from server.conversation.turn_state import TurnState
from server.conversation.turn_rules import (
    check_speaker_switch_rule,
    check_low_similarity_question_rule,
    check_similar_text_continue_rule,
    check_asr_final_rule,
    check_question_pause_rule,
    check_short_text_rule,
)


class TurnManager:
    """
    负责维护气泡生成、判断是否可以截断合并（产生一轮问答）的核心状态机。
    剥离了旧代码中 `got_final`, `draft_sent` 散乱的局部变量标记。
    """

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
        asr_baseline: str = "",
    ) -> Dict[str, Any]:
        """开启并进入新的一轮对话"""
        now_ts = time.monotonic()
        self.current_turn = {
            "id": self.next_turn_id,
            "text": text,
            "norm": norm_text,
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
        incoming_norm_text: str,
        incoming_speaker: Optional[int],
        source_role: str,
        asr_got_final: bool = False,
    ) -> bool:
        """
        判断是否要强行闭合上一轮，进入全新的一个气泡轮次。
        核心逻辑：基础校验 → 前置规则（短文本）→ 核心规则依次判断
        """
        # 基础校验1：当前轮次不存在/已关闭
        turn = self.current_turn
        if not turn or turn.get("closed"):
            self.last_new_turn_eval = {"trigger": False, "reason": "no_turn"}
            return False

        # 计算基础参数（复用参数，避免重复计算）
        now_ts = time.monotonic()
        prev_norm = turn.get("norm", "")
        speech_gap = now_ts - turn.get("audio_last_ts", now_ts)
        turn_speaker = turn.get("speaker_id")
        speaker_switched = (
            incoming_speaker is not None
            and turn_speaker is not None
            and incoming_speaker != turn_speaker
        )

        # 基础校验2：面试者发言时，禁止开新轮
        if source_role == "candidate":
            self.last_new_turn_eval = {
                "trigger": False,
                "reason": "candidate_source_active",
                "speaker_switched": speaker_switched,
            }
            return False

        # 前置规则：短文本判断
        short_text_result, short_text_reason = check_short_text_rule(
            prev_norm=prev_norm,
            incoming_norm_text=incoming_norm_text,
            incoming_speaker=incoming_speaker,
            turn_speaker=turn_speaker,
            asr_got_final=asr_got_final,
            speech_gap=speech_gap,
        )
        if short_text_result is False:
            self.last_new_turn_eval = {
                "trigger": False,
                "reason": short_text_reason,
                "speaker_switched": speaker_switched,
            }
            return False
        if short_text_result is True:
            self.last_new_turn_eval = {"trigger": True, "reason": short_text_reason}
            return True

        # 核心规则1：声纹切换规则
        speaker_rule_trigger, speaker_rule_reason = check_speaker_switch_rule(
            incoming_speaker=incoming_speaker,
            turn_speaker=turn_speaker,
            incoming_norm_text=incoming_norm_text,
            prev_norm=prev_norm,
            speech_gap=speech_gap,
        )
        if speaker_rule_trigger:
            self.last_new_turn_eval = {"trigger": True, "reason": speaker_rule_reason}
            return True

        # 核心规则2：低相似+提问特征规则
        low_sim_rule_trigger, low_sim_rule_reason = check_low_similarity_question_rule(
            incoming_norm_text=incoming_norm_text,
            prev_norm=prev_norm,
            speech_gap=speech_gap,
        )
        if low_sim_rule_trigger:
            self.last_new_turn_eval = {"trigger": True, "reason": low_sim_rule_reason}
            return True

        # 核心规则3：高相似延续规则（禁止切分）
        similar_text_rule_trigger, similar_text_rule_reason = (
            check_similar_text_continue_rule(
                incoming_speaker=incoming_speaker,
                turn_speaker=turn_speaker,
                incoming_norm_text=incoming_norm_text,
                prev_norm=prev_norm,
            )
        )
        if similar_text_rule_trigger:
            self.last_new_turn_eval = {
                "trigger": False,
                "reason": similar_text_rule_reason,
            }
            return False

        # 核心规则4：ASR终结信号规则
        asr_result, asr_reason = check_asr_final_rule(
            asr_got_final=asr_got_final,
            incoming_speaker=incoming_speaker,
            turn_speaker=turn_speaker,
            turn_text=turn.get("text", ""),
            speech_gap=speech_gap,
        )
        if asr_result is False:
            self.last_new_turn_eval = {"trigger": False, "reason": asr_reason}
            return False
        if asr_result is True:
            self.last_new_turn_eval = {"trigger": True, "reason": asr_reason}
            return True

        # 核心规则5：提问+长停顿规则
        question_pause_trigger, question_pause_reason = check_question_pause_rule(
            turn_text=turn.get("text", ""), speech_gap=speech_gap
        )
        if question_pause_trigger:
            self.last_new_turn_eval = {"trigger": True, "reason": question_pause_reason}
            return True

        # 所有规则均未触发
        self.last_new_turn_eval = {"trigger": False, "reason": "not_enough_signal"}
        return False
