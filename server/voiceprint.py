"""轻量声纹追踪器 — 基于 PCM 片段统计特征。

非生物级声纹识别，而是用于轮次管理和说话人切换检测的快速在线启发式方案。
"""

from __future__ import annotations

import math
import time
from collections import deque
import audioop


def _distance(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


class VoiceprintTracker:
    def __init__(
        self,
        assign_threshold: float = 0.30,
        min_rms: int = 110,
        lookback_seconds: float = 1.2,
        max_speakers: int = 8,
        ema_alpha: float = 0.20,
    ):
        self.assign_threshold = assign_threshold
        self.min_rms = min_rms
        self.lookback_seconds = lookback_seconds
        self.max_speakers = max_speakers
        self.ema_alpha = ema_alpha
        self._prototypes: dict[int, tuple[float, ...]] = {}
        self._next_id = 1
        self._events = deque()

    @staticmethod
    def _extract_features(pcm16_mono: bytes) -> tuple[float, ...] | None:
        if not pcm16_mono or len(pcm16_mono) < 320:
            return None
        try:
            rms = audioop.rms(pcm16_mono, 2)
            zc = audioop.cross(pcm16_mono, 2)
            avgpp = audioop.avgpp(pcm16_mono, 2)
            peak = audioop.max(pcm16_mono, 2)
        except audioop.error:
            return None
        if rms <= 0:
            return None

        # 特征归一化到 [0, 1] 近似范围
        loud = min(1.0, math.log1p(rms) / math.log1p(32767))
        zcr = min(1.0, zc / max(1, len(pcm16_mono) // 2))
        pp = min(1.0, avgpp / 32767)
        pk = min(1.0, peak / 32767)
        return (loud, zcr, pp, pk)

    def _assign(self, feat: tuple[float, ...]) -> int:
        if not self._prototypes:
            sid = self._next_id
            self._next_id += 1
            self._prototypes[sid] = feat
            return sid

        best_id = None
        best_dist = 1e9
        for sid, proto in self._prototypes.items():
            d = _distance(feat, proto)
            if d < best_dist:
                best_id = sid
                best_dist = d

        if best_id is not None and best_dist <= self.assign_threshold:
            p = self._prototypes[best_id]
            a = self.ema_alpha
            self._prototypes[best_id] = tuple((1 - a) * x + a * y for x, y in zip(p, feat))
            return best_id

        if len(self._prototypes) >= self.max_speakers and best_id is not None:
            # 说话人槽位已满，回退到最近的说话人
            p = self._prototypes[best_id]
            a = self.ema_alpha * 0.6
            self._prototypes[best_id] = tuple((1 - a) * x + a * y for x, y in zip(p, feat))
            return best_id

        sid = self._next_id
        self._next_id += 1
        self._prototypes[sid] = feat
        return sid

    def update_audio(self, pcm16_mono: bytes, ts: float | None = None) -> int | None:
        ts = time.monotonic() if ts is None else ts
        feat = self._extract_features(pcm16_mono)
        if feat is None:
            return None
        try:
            rms = audioop.rms(pcm16_mono, 2)
        except audioop.error:
            return None
        if rms < self.min_rms:
            return None
        sid = self._assign(feat)
        self._events.append((ts, sid))

        # 清理超出回溯窗口的旧事件（带少量余量）
        horizon = self.lookback_seconds * 2.0
        while self._events and (ts - self._events[0][0]) > horizon:
            self._events.popleft()
        return sid

    def dominant_speaker(self, ts: float | None = None) -> int | None:
        ts = time.monotonic() if ts is None else ts
        if not self._events:
            return None
        scores: dict[int, float] = {}
        for evt_ts, sid in self._events:
            age = ts - evt_ts
            if age < 0 or age > self.lookback_seconds:
                continue
            # 越新的帧权重越高
            w = 1.0 - (age / max(self.lookback_seconds, 1e-6)) * 0.6
            scores[sid] = scores.get(sid, 0.0) + max(0.1, w)
        if not scores:
            return None
        return max(scores.items(), key=lambda kv: kv[1])[0]
