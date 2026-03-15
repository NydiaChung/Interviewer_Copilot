"""轻量 Trace 工具 — 替代 WebSocket handler 中的 _trace 闭包。"""

import json
import time

from server.config import TRACE_ENABLED


class Tracer:
    """每个 WebSocket 连接创建一个 Tracer 实例。"""

    def __init__(self, trace_id: str, session_id: str):
        self.trace_id = trace_id
        self.session_id = session_id
        self._seq = 0

    def log(self, event: str, **fields) -> None:
        if not TRACE_ENABLED:
            return
        self._seq += 1
        payload = {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "seq": self._seq,
            "event": event,
            "mono_ts": round(time.monotonic(), 3),
        }
        payload.update(fields)
        try:
            print("[Trace] " + json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            print(f"[Trace] {event} {fields}")
