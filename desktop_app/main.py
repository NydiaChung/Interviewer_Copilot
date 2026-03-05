import os
import sys
import asyncio
import threading
import websockets
import json
import time
import base64
from PyQt6.QtWidgets import QApplication
from overlay_ui import OverlayUI
from control_panel import ControlPanelUI

try:
    from audio_capture import AudioCapture

    AUDIO_AVAILABLE = True
except Exception as e:
    print(f"[Audio] PyAudio not available: {e}")
    AUDIO_AVAILABLE = False
    AudioCapture = None

# Use the local backend url
WS_URL = os.getenv("WS_URL", "ws://localhost:8000/ws/audio")
DUAL_STREAM_MODE = os.getenv("DUAL_STREAM_MODE", "true").lower()


class DesktopApp:
    def __init__(self):
        # 1. Start Application Instance
        self.app = QApplication(sys.argv)
        # Keep app alive even if temporary windows are hidden/closed.
        self.app.setQuitOnLastWindowClosed(False)
        self.overlay = None
        self.audio = None
        self.loop = None
        self.ws_thread = None
        self.audio_queue = None
        self.latest_answer_seq = 0
        self.latest_outline_seq = 0
        self._last_source_meta_ts = 0.0
        self._last_source_dominant = ""

        # 2. Start Control Panel
        self.control_panel = ControlPanelUI()
        self.control_panel.start_interview_signal.connect(self.start_interview)
        self.control_panel.end_interview_signal.connect(self.trigger_end_session)
        self.control_panel.show()

    def start_interview(self, jd, resume):
        """Called by the Control Panel when Start is clicked and context is set."""
        if self.ws_thread and self.ws_thread.is_alive():
            return
        self.latest_answer_seq = 0
        self.latest_outline_seq = 0
        self._last_source_meta_ts = 0.0
        self._last_source_dominant = ""

        # 3. Show the overlay
        self.overlay = OverlayUI()
        self.overlay.show()

        # 4. Setup signals from overlay
        self.overlay.end_session_signal.connect(self.trigger_end_session)
        self.overlay.send_text_signal.connect(self.on_manual_text)

        # 5. Setup Audio capture (graceful if PyAudio not installed)
        if AUDIO_AVAILABLE:
            try:
                self.audio = AudioCapture(
                    self.on_audio_data,
                    self.on_audio_meta,
                    dual_stream_mode=DUAL_STREAM_MODE,
                )
            except Exception as e:
                print(f"[Audio] Failed to init AudioCapture: {e}")
                self.audio = None
                self.overlay.update_signal.emit(
                    "incremental",
                    "⚠️ 麦克风无法初始化（PyAudio / portaudio 未安装）——可用下方输入框手动提问",
                )
        else:
            self.audio = None
            self.overlay.update_signal.emit(
                "incremental",
                "⚠️ PyAudio 未安装，语音采集关闭。可用下方输入框手动提问。",
            )

        # 6. Setup Asyncio loop for WebSockets
        self.loop = asyncio.new_event_loop()
        self.ws_thread = threading.Thread(target=self.start_async_loop, daemon=True)
        self.ws_thread.start()

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.ws_client())

    def trigger_end_session(self):
        print("[Desktop] Ending session and requesting analysis...")
        if self.overlay:
            self.overlay.update_signal.emit(
                "answer", "正在请求AI生成面试复盘报告，请稍候..."
            )

        self._enqueue_ws_payload(b"END_SESSION_CMD")

    def on_manual_text(self, text: str):
        """Called when user types text in the overlay input box."""
        # 以 str 类型存入队列，与 bytes 音频数据区分，避免 UTF-8 解码错误
        payload = json.dumps({"command": "manual_question", "text": text})
        self._enqueue_ws_payload(payload)  # str, NOT encoded bytes

    def on_audio_data(self, audio_bytes, channel: str = None):
        """Called directly by PyAudio in its C-thread. Thread-safe push to asyncio queue."""
        if channel:
            # 双向/双流模式：将音频转换成 base64 存入字典再转回 str 以 JSON 给队列处理
            payload = json.dumps(
                {
                    "type": "audio",
                    "channel": channel,
                    "data": base64.b64encode(audio_bytes).decode("ascii"),
                }
            )
            self._enqueue_ws_payload(payload)
        else:
            self._enqueue_ws_payload(audio_bytes)

    def on_audio_meta(self, meta: dict):
        """Called by AudioCapture with source activity metadata."""
        if not isinstance(meta, dict):
            return
        now = time.monotonic()
        dominant = str(meta.get("dominant_source", "unknown"))
        # 降低控制帧频率：源发生变化时立即上报，否则 250ms 采样上报。
        if (
            dominant == self._last_source_dominant
            and (now - self._last_source_meta_ts) < 0.25
        ):
            return
        self._last_source_meta_ts = now
        self._last_source_dominant = dominant
        payload = json.dumps(
            {
                "command": "source_activity",
                "dominant_source": dominant,
                "mic_rms": int(meta.get("mic_rms", 0)),
                "system_rms": int(meta.get("system_rms", 0)),
            }
        )
        self._enqueue_ws_payload(payload)

    def _enqueue_ws_payload(self, payload):
        if not self.loop or not self.audio_queue:
            return
        if self.loop.is_closed() or not self.loop.is_running():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.audio_queue.put(payload), self.loop)
        except RuntimeError:
            # Loop is shutting down; dropping late payload is expected.
            return

    async def ws_client(self):
        self.audio_queue = asyncio.Queue()
        if self.audio:
            self.audio.start()

        try:
            async with websockets.connect(WS_URL) as websocket:
                print("[Desktop] Connected to Interview Copilot backend.")

                # Receiver task
                async def receive_from_server():
                    try:
                        while True:
                            message = await websocket.recv()
                            data = json.loads(message)
                            msg_type = data.get("type", "answer")
                            raw_seq = data.get("seq", 0)
                            try:
                                seq = int(raw_seq or 0)
                            except (TypeError, ValueError):
                                seq = 0

                            # 丢弃过期消息，避免旧问题答案覆盖新问题答案
                            if msg_type == "outline":
                                if seq and seq < self.latest_answer_seq:
                                    continue
                                if seq and seq < self.latest_outline_seq:
                                    continue
                                if seq:
                                    self.latest_outline_seq = seq
                            elif msg_type == "answer":
                                if seq and seq < self.latest_answer_seq:
                                    continue
                                if seq:
                                    self.latest_answer_seq = seq

                            # 将完整 JSON 数据序列化后传给 overlay，使其能解析
                            # speaker_role、question_id、question 等字段
                            if self.overlay:
                                payload_str = json.dumps(data, ensure_ascii=False)
                                self.overlay.update_signal.emit(msg_type, payload_str)

                            # If it's the final analysis, tell the control panel to refresh
                            if msg_type == "analysis":
                                self.control_panel.interview_ended_signal.emit()

                    except websockets.exceptions.ConnectionClosed:
                        print("[Desktop] Backend connection closed.")
                        # Ensure control panel is visible if it was hidden.
                        self.control_panel.interview_ended_signal.emit()

                recv_task = asyncio.create_task(receive_from_server())

                # Sender task (send audio chunks)
                _send_count = 0
                while True:
                    chunk = await self.audio_queue.get()
                    if chunk == b"END_SESSION_CMD":
                        # 结束信号
                        await websocket.send(json.dumps({"command": "end_session"}))
                        if self.audio:
                            self.audio.stop()
                    elif isinstance(chunk, str):
                        # 文本命令（manual_question 等）
                        if not chunk.startswith('{"command": "source_activity"'):
                            print(f"[Desktop] Sending text command: {chunk[:80]}")
                        await websocket.send(chunk)
                    else:
                        # 音频二进制帧
                        _send_count += 1
                        if _send_count % 20 == 1:
                            print(f"[Desktop] → 音频帧 #{_send_count}  {len(chunk)}B")
                        await websocket.send(chunk)

        except Exception as e:
            print(f"[Desktop] WebSocket Error: {e}")
            if self.overlay:
                self.overlay.update_signal.emit("answer", f"Error: {e}")
        finally:
            if self.audio:
                self.audio.stop()
            self.audio_queue = None

    def run(self):
        # Run PyQt Event Loop (blocking main thread)
        sys.exit(self.app.exec())


if __name__ == "__main__":
    client = DesktopApp()
    client.run()
