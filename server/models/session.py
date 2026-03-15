"""面试会话状态管理。"""

import asyncio
import time


class InterviewSession:
    """单次面试连接的上下文状态。

    所有与单次连接强相关的全局变量均被收束于此，
    消解全局共用带来的线程安全问题。
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # 核心上下文
        self.jd_text: str = ""
        self.resume_text: str = ""

        # 会话属性
        self.is_active = True
        self.start_time = time.time()

        # 序列号
        self.latest_answer_seq = 0
        self.latest_outline_seq = 0

        # 历史记录
        self.transcript: list[dict] = []

        # 会话锁
        self.lock = asyncio.Lock()

    def set_context(self, jd: str, resume: str):
        """设定本次连接的职位和简历上下文。"""
        self.jd_text = jd
        self.resume_text = resume

    def is_context_ready(self) -> bool:
        """检查前置材料是否就绪。"""
        return bool(self.jd_text and self.resume_text)

    def append_transcript(
        self,
        seq: int,
        source: str,
        question_id: int,
        question: str,
        answer: str,
    ):
        """向本次会话历史追加问答记录。"""
        self.transcript.append(
            {
                "seq": seq,
                "source": source,
                "question_id": question_id,
                "面试官的问题": question,
                "AI参考回答": answer,
            }
        )

    def get_sorted_transcript(self, limit: int = None) -> list[dict]:
        """获取按 seq 排序的历史记录。"""
        sorted_records = sorted(self.transcript, key=lambda x: x["seq"])
        if limit:
            sorted_records = sorted_records[-limit:]
        return sorted_records

    def format_history_for_llm(self) -> str:
        """将历史转化为 LLM 可消费的文本。"""
        lines: list[str] = []
        for turn in self.get_sorted_transcript():
            q = turn.get("面试官的问题", "")
            a = turn.get("AI参考回答", "")
            lines.append(f"【面试官】: {q}")
            lines.append(f"【AI助攻参考】: {a}")
            lines.append("---")
        return "\n".join(lines)
