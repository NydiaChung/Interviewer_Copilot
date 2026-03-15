"""全局配置常量 — 单一来源。

所有阈值、超时、环境变量开关统一在此管理，
其他模块通过 ``from server.config import XXX`` 引用。
"""

import os

# ---------------------------------------------------------------------------
# LLM 超时 & 兜底文本
# ---------------------------------------------------------------------------
LLM_OUTLINE_TIMEOUT_SECONDS = 8
LLM_ANSWER_TIMEOUT_SECONDS = 18
LLM_ANALYSIS_TIMEOUT_SECONDS = 45
ANSWER_FALLBACK_TEXT = (
    "抱歉，我刚才没来得及生成完整回答。请让我复述一遍这个问题，我会马上给你一个结构化回答。"
)
ANALYSIS_FALLBACK_TEXT = "本次复盘生成超时或失败，请稍后重试。"

# ---------------------------------------------------------------------------
# 问题 / 轮次关闭
# ---------------------------------------------------------------------------
QUESTION_CLOSE_SILENCE_SECONDS = 0.9
QUESTION_FORCE_CLOSE_SECONDS = 2.6

# ---------------------------------------------------------------------------
# 轮次切换判断阈值
# ---------------------------------------------------------------------------
NEW_QUESTION_SIMILARITY_THRESHOLD = 0.45
VOICEPRINT_SWITCH_MIN_GAP_SECONDS = 0.35
VOICEPRINT_SWITCH_SIMILARITY_THRESHOLD = 0.72

# 停顿时间阈值（秒）— 用于 turn_rules
QUESTION_PAUSE_SHORT_THRESHOLD = 0.22
QUESTION_PAUSE_MID_THRESHOLD = 0.4
QUESTION_PAUSE_LONG_THRESHOLD = 0.55

# 短文本阈值
SHORT_TEXT_MIN_PREV = 10
SHORT_TEXT_MIN_INCOMING = 6
SHORT_TEXT_MIN_INCOMING_SWITCH = 4

# ---------------------------------------------------------------------------
# 声纹
# ---------------------------------------------------------------------------
VOICEPRINT_CLOSE_SILENCE_SECONDS = 0.35
SPEAKER_CONFIRM_FRAMES = 4
SPEAKER_CONFIRM_MAX_GAP_SECONDS = 0.5

# ---------------------------------------------------------------------------
# 音频 & ASR
# ---------------------------------------------------------------------------
TURN_ACTIVE_AUDIO_RMS = 220
ANSWER_STREAM_INTERVAL_SECONDS = 0.04
CLOSE_WATCHER_POLL_SECONDS = 0.25

# 音源角色判定
SOURCE_ACTIVITY_FRESH_SECONDS = 1.2
SOURCE_TAKEOVER_CLOSE_WINDOW_SECONDS = 1.8
USE_AUDIO_SOURCE_FOR_ROLE_SEPARATION = True

# ---------------------------------------------------------------------------
# Tracing & ASR 稳定性
# ---------------------------------------------------------------------------
TRACE_ENABLED = os.getenv(
    "TRACE_ENABLED", "1"
).lower() not in ("0", "false", "off")
TRACE_AUDIO_SAMPLE_EVERY = int(os.getenv("TRACE_AUDIO_SAMPLE_EVERY", "80"))
ASR_STALL_ACTIVE_FRAMES = int(os.getenv("ASR_STALL_ACTIVE_FRAMES", "35"))
ASR_RESTART_COOLDOWN_SECONDS = float(
    os.getenv("ASR_RESTART_COOLDOWN_SECONDS", "8.0")
)
CANDIDATE_ASR_RETRY_SECONDS = float(
    os.getenv("CANDIDATE_ASR_RETRY_SECONDS", "6.0")
)
