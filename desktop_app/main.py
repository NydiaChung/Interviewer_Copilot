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

        # 初始化所有核心状态变量（初始值为None/默认值）
        self.overlay = None  # 面试浮层界面（初始未创建）
        self.audio = None  # 音频采集模块（初始未初始化）
        self.loop = None  # 异步事件循环（初始未创建）
        self.ws_thread = None  # WebSocket通信线程（初始未启动）
        self.audio_queue = None  # 音频数据队列（用于缓存音频数据）
        self.latest_answer_seq = 0  # 最新回答序列号（去重/排序用）
        self.latest_outline_seq = 0  # 最新大纲序列号
        self._last_source_meta_ts = 0.0  # 最后一次音频元数据时间戳
        self._last_source_dominant = ""  # 最后一次主导说话人（面试官/候选人）

        # 控制面板 初始化&交互绑定
        self.control_panel = ControlPanelUI()  # 创建控制面板界面实例
        # 绑定控制面板的信号到对应处理函数
        self.control_panel.start_interview_signal.connect(self.start_interview)
        self.control_panel.end_interview_signal.connect(self.trigger_end_session)
        self.control_panel.show()  # 显示控制面板界面

    def start_interview(self, jd, resume):
        """当用户在控制面板点击「开始」按钮且上下文（JD / 简历）已设置时触发"""
        # 防止重复启动：如果WebSocket线程已在运行，直接返回
        if self.ws_thread and self.ws_thread.is_alive():
            return

        # 初始化会话状态变量：每次启动新面试时，清空历史序列号、时间戳等，保证会话独立性。
        self.latest_answer_seq = 0  # 最新回答的序列号（用于去重/排序）
        self.latest_outline_seq = 0  # 最新大纲的序列号
        self._last_source_meta_ts = 0.0  # 最后一次音频元数据的时间戳
        self._last_source_dominant = ""  # 最后一次识别的主导说话人（面试官/候选人）

        # 创建并显示面试浮层界面（OverlayUI）
        self.overlay = OverlayUI()
        self.overlay.show()

        # 绑定浮层界面的信号槽
        self.overlay.end_session_signal.connect(self.trigger_end_session)  # 结束会话
        self.overlay.send_text_signal.connect(self.on_manual_text)  # 手动输入问题

        # 启动音频捕获（如果 PyAudio 未安装，则优雅降级）
        if AUDIO_AVAILABLE:  # 先判断PyAudio是否安装（全局常量）
            try:
                # 初始化音频采集模块
                self.audio = AudioCapture(
                    self.on_audio_data,  # 音频数据回调（接收PCM数据）
                    self.on_audio_meta,  # 音频元数据回调（比如说话人、时间戳）
                    dual_stream_mode=DUAL_STREAM_MODE,  # 是否开启双通道（对应之前的面试官/候选人）
                )
            except Exception as e:
                # 音频采集初始化失败（比如portaudio未装），友好提示
                print(f"[Audio] Failed to init AudioCapture: {e}")
                self.audio = None
                self.overlay.update_signal.emit(
                    "incremental",
                    "⚠️ 麦克风无法初始化（PyAudio / portaudio 未安装）——可用下方输入框手动提问",
                )
        else:
            # PyAudio未安装，直接关闭音频采集，提示用户
            self.audio = None
            self.overlay.update_signal.emit(
                "incremental",
                "⚠️ PyAudio 未安装，语音采集关闭。可用下方输入框手动提问。",
            )

        # 启动异步循环（内部会连接WebSocket）
        self.loop = asyncio.new_event_loop()  # 创建异步事件循环
        self.ws_thread = threading.Thread(
            target=self.start_async_loop, daemon=True
        )  # 创建守护线程
        self.ws_thread.start()  # 启动线程，运行异步循环（内部会连接WebSocket）

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.ws_client())

    def trigger_end_session(self):
        print("[Desktop] 会话结束请求报告...")
        if self.overlay:
            self.overlay.update_signal.emit(
                "answer", "正在请求AI生成面试复盘报告，请稍候..."
            )
        self._enqueue_ws_payload(b"END_SESSION_CMD")

    # 手动输入文本处理
    def on_manual_text(self, text: str):
        """Called when user types text in the overlay input box."""
        # 以 str 类型存入队列，与 bytes 音频数据区分，避免 UTF-8 解码错误
        payload = json.dumps({"command": "manual_question", "text": text})
        self._enqueue_ws_payload(payload)  # str, NOT encoded bytes

    # 语音数据处理
    # audio_bytes：PyAudio 采集到的二进制音频数据（PCM 格式，字节流）
    # channel：可选。双流模式下为 "interviewer" 或 "candidate"，单流模式下为 None。
    def on_audio_data(self, audio_bytes, channel: str = None):
        """Called directly by PyAudio in its C-thread. Thread-safe push to asyncio queue."""
        if channel:
            # 双向/双流模式：将音频转换成 base64 存入字典再转回 str 以 JSON
            """payload示例
             {
                "type": "audio",
                "channel": "interviewer",
                "data": "UklGRl9CAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQ=="
            }
            """
            payload = json.dumps(
                {
                    "type": "audio",
                    "channel": channel,
                    "data": base64.b64encode(audio_bytes).decode("ascii"),
                }
            )
            self._enqueue_ws_payload(payload)
        else:
            # 单通道模式：直接转发二进制音频数据
            self._enqueue_ws_payload(audio_bytes)

    # 语音元数据处理
    # 由 AudioCapture 调用，传入的是 “音频源活动元数据”（比如谁在说话、音量大小）
    def on_audio_meta(self, meta: dict):
        # 前置校验：元数据不是字典 → 直接返回，不处理
        if not isinstance(meta, dict):
            return

        # 获取当前时间（monotonic 是单调递增时间，不受系统时间修改影响，适合计算间隔）
        now = time.monotonic()
        # 提取「主导说话人」：比如 "interviewer"（面试官）/"candidate"（候选人）/"unknown"
        dominant = str(meta.get("dominant_source", "unknown"))
        # 核心频率控制逻辑：降低控制帧上报频率
        # 条件1：主导说话人和上一次一致；条件2：距离上次上报不足 250ms → 跳过本次上报
        if (
            dominant == self._last_source_dominant
            and (now - self._last_source_meta_ts) < 0.25
        ):
            return
        # 更新时间戳和主导说话人
        self._last_source_meta_ts = now
        self._last_source_dominant = dominant

        # 构造并发送控制帧（JSON 字符串）
        payload = json.dumps(
            {
                "command": "source_activity",  # 命令类型：音频源活动状态
                "dominant_source": dominant,  # 当前主导说话人
                "mic_rms": int(
                    meta.get("mic_rms", 0)
                ),  # 麦克风音量（RMS 均方根，表征音量大小）
                "system_rms": int(meta.get("system_rms", 0)),  # 系统音频音量
            }
        )
        self._enqueue_ws_payload(payload)

    # 线程安全的异步队列写入工具
    def _enqueue_ws_payload(self, payload):
        # 前置校验1：异步循环或队列未初始化 → 直接返回，不处理
        if not self.loop or not self.audio_queue:
            return
        # 前置校验2：异步循环已关闭/未运行 → 直接返回，不处理
        if self.loop.is_closed() or not self.loop.is_running():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.audio_queue.put(payload), self.loop)
        except RuntimeError:
            # Loop is shutting down; dropping late payload is expected.
            return

    async def ws_client(self):
        # 1. 初始化音频队列（异步队列，用于缓存音频数据）
        self.audio_queue = asyncio.Queue()
        # 2. 如果音频采集模块已初始化，启动采集（开始录音频）
        if self.audio:
            self.audio.start()

        try:
            # 3. 建立 WebSocket 连接（async with 是异步上下文管理器，自动处理连接关闭）
            async with websockets.connect(WS_URL) as websocket:
                print("[Desktop] Connected to Interview Copilot backend.")

                # Receiver task: 接收后端消息的异步任务
                async def receive_from_server():
                    try:
                        while True:  # 循环监听后端消息
                            message = await websocket.recv()  # 异步接收消息（不阻塞）
                            data = json.loads(message)  # 解析 JSON 消息
                            msg_type = data.get(
                                "type", "answer"
                            )  # 消息类型（answer/outline/analysis）
                            raw_seq = data.get("seq", 0)  # 消息序列号（用于去重）
                            try:
                                seq = int(raw_seq or 0)
                            except (TypeError, ValueError):
                                seq = 0

                            # 核心逻辑：丢弃过期消息（避免旧答案覆盖新答案）
                            if msg_type == "outline":
                                if seq and seq < self.latest_answer_seq:
                                    continue  # 序列号更小，是旧消息，跳过
                                if seq and seq < self.latest_outline_seq:
                                    continue
                                if seq:
                                    self.latest_outline_seq = seq  # 更新最新序列号
                            elif msg_type == "answer":
                                if seq and seq < self.latest_answer_seq:
                                    continue
                                if seq:
                                    self.latest_answer_seq = seq

                            # 把后端消息转发给浮层界面展示
                            if self.overlay:
                                # 序列化数据（保证中文不转义），通过信号发给 overlay
                                payload_str = json.dumps(data, ensure_ascii=False)
                                self.overlay.update_signal.emit(msg_type, payload_str)

                            # 如果是分析结果（面试结束），通知控制面板刷新
                            if msg_type == "analysis":
                                self.control_panel.interview_ended_signal.emit()

                    except websockets.exceptions.ConnectionClosed:
                        # 连接关闭时的处理：打印日志，通知控制面板
                        print("[Desktop] 后端连接关闭.")
                        self.control_panel.interview_ended_signal.emit()

                # 创建并启动接收任务（异步任务，不阻塞主线程），和下面发数据同时进行
                recv_task = asyncio.create_task(receive_from_server())

                # Sender task ：发送数据给后端（音频 / 文本命令）
                _send_count = 0  # 音频帧计数（用于日志）
                while True:  # 循环从队列取数据发送
                    chunk = (
                        await self.audio_queue.get()
                    )  # 异步取队列数据（队列为空时等待）

                    # 情况1：收到结束会话信号 → 发送结束命令，停止音频采集
                    if chunk == b"END_SESSION_CMD":
                        await websocket.send(json.dumps({"command": "end_session"}))
                        if self.audio:
                            self.audio.stop()

                    # 情况2：文本命令（比如手动输入的问题、说话人活动状态）
                    elif isinstance(chunk, str):
                        if not chunk.startswith('{"command": "source_activity"'):
                            print(f"[Desktop] 发送文本命令: {chunk[:80]}")
                        await websocket.send(chunk)

                    # 情况3：音频二进制数据（PCM 帧）
                    else:
                        _send_count += 1
                        if _send_count % 20 == 1:  # 每20帧打印一次日志（避免刷屏）
                            print(f"[Desktop] → 音频帧 #{_send_count}  {len(chunk)}B")
                        await websocket.send(chunk)

        except Exception as e:
            # 捕获所有异常（连接失败、发送/接收出错等）
            print(f"[Desktop] WebSocket Error: {e}")
            if self.overlay:
                self.overlay.update_signal.emit("answer", f"Error: {e}")
        finally:
            # 无论是否异常，最终都停止音频采集，清空队列
            if self.audio:
                self.audio.stop()
            self.audio_queue = None

    def run(self):
        # Run PyQt Event Loop (blocking main thread)
        sys.exit(self.app.exec())


if __name__ == "__main__":
    client = DesktopApp()
    client.run()
