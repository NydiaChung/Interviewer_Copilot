"""WebSocket 连接级状态 — 替代 audio_websocket 中 40+ nonlocal 变量。"""

from __future__ import annotations

import asyncio
import time
import wave
from typing import TYPE_CHECKING

from server.asr.base import ASRProvider
from server.conversation.turn_manager import TurnManager
from server.conversation.intent_detector import IntentReadinessDetector
from server.voiceprint import VoiceprintTracker
from server.config import TURN_ACTIVE_AUDIO_RMS

if TYPE_CHECKING:
    from fastapi import WebSocket
    from server.models.session import InterviewSession
    from server.utils.tracing import Tracer


class ConnectionState:
    """每个 WebSocket 连接创建一个实例，所有 handler 共享此对象协作。"""

    def __init__(
        self,
        websocket: WebSocket,
        session: InterviewSession,
        tracer: Tracer,
        session_id: str,
        trace_id: str,
        wave_file: wave.Wave_write,
        transcript_file_path: str,
    ):
        # 外部依赖
        self.websocket = websocket
        self.session = session
        self.tracer = tracer
        self.session_id = session_id
        self.trace_id = trace_id
        self.wave_file = wave_file
        self.transcript_file_path = transcript_file_path

        # ASR
        self.asr_processor: ASRProvider | None = None
        self.asr_candidate: ASRProvider | None = None
        self.candidate_last_start_attempt_ts: float = 0.0

        # 轮次管理
        self.turn_manager = TurnManager()
        self.intent_detector = IntentReadinessDetector()

        # 声纹
        self.voiceprint_tracker = VoiceprintTracker(
            min_rms=TURN_ACTIVE_AUDIO_RMS,
            assign_threshold=0.45,
        )
        self.last_dominant_speaker: int | None = None
        self.last_speaker_change_ts: float = 0.0
        self.speaker_candidate: int | None = None
        self.speaker_candidate_count: int = 0
        self.speaker_candidate_last_ts: float = 0.0

        # 回答调度
        self.next_answer_seq: int = 1
        self.last_answer_trigger_text: str = ""
        self.last_answer_trigger_ts: float = 0.0
        self.answer_generation_lock = asyncio.Lock()

        # 异步任务
        self.background_tasks: set[asyncio.Task] = set()
        self.answer_tasks: set[asyncio.Task] = set()
        self.outline_task: asyncio.Task | None = None
        self.close_check_task: asyncio.Task | None = None

        # ASR 全局累积文本
        self.asr_global_text: str = ""

        # 音源活跃度
        self.source_activity: dict = {
            "dominant_source": "unknown",
            "mic_rms": 0,
            "system_rms": 0,
            "ts": 0.0,
            "change_ts": 0.0,
        }

        # 说话人角色映射
        self.speaker_mapping_state: dict = {}

        # ASR 稳定性监控
        self.main_active_frames_since_text: int = 0
        self.main_last_text_ts: float = 0.0
        self.last_main_asr_restart_ts: float = 0.0

        # 接收计数
        self.recv_count: int = 0

        # 候选人独立转写记录
        self.session_transcript: list[dict] = []

        # 事件循环引用
        self.loop: asyncio.AbstractEventLoop | None = None

    def trace(self, event: str, **fields):
        """快捷 trace 方法。"""
        self.tracer.log(event, **fields)
