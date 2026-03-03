"""
ASR 模块 — 支持多提供商切换（豆包/通义）

通过 .env 中的 ASR_PROVIDER (doubao | aliyun) 切换。
"""

import asyncio
import json
import os
import struct
import threading
import uuid
import abc

import websockets

# ── 认证信息从 .env 加载 ──
PROVIDER = os.getenv("ASR_PROVIDER", "doubao").lower()

# 豆包配置
DOUBAO_APP_ID = os.getenv("DOUBAO_APP_ID", "")
DOUBAO_ACCESS_TOKEN = os.getenv("DOUBAO_ACCESS_TOKEN", "")
DOUBAO_CLUSTER = os.getenv("DOUBAO_CLUSTER", "volcengine_streaming_common")
DOUBAO_RESOURCE_ID = os.getenv("DOUBAO_RESOURCE_ID", "volc.bigasr.sauc.duration")

# 阿里云配置（通义听悟/DashScope）
ALIYUN_AK_ID = os.getenv("TINGWU_ACCESS_KEY_ID", "")
ALIYUN_AK_SECRET = os.getenv("TINGWU_ACCESS_KEY_SECRET", "")
ALI_APP_KEY = os.getenv("TINGWU_APP_KEY", "")


class ASRProvider(abc.ABC):
    """ASR 提供商基类"""

    def __init__(self):
        self.on_text_update = None
        self.loop = None
        self.is_started = False

    def set_callback(self, on_text_update_func, loop):
        self.on_text_update = on_text_update_func
        self.loop = loop

    @abc.abstractmethod
    def start(self):
        pass

    @abc.abstractmethod
    def add_audio(self, audio_chunk: bytes):
        pass

    @abc.abstractmethod
    def stop(self):
        pass


class DoubaoProvider(ASRProvider):
    """豆包 (ByteDance) 流式 ASR 实现"""

    BASE_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"

    # 帧头常量
    HEADER_VERSION_SIZE = b"\x11"
    HEADER_FULL_CLIENT = b"\x10\x10\x00"
    HEADER_AUDIO = b"\x20\x00\x00"
    HEADER_AUDIO_LAST = b"\x22\x00\x00"

    def __init__(self):
        super().__init__()
        self._ws_loop = None
        self._audio_queue = None
        self._thread = None
        self._audio_count = 0
        self._recv_buffer = bytearray()
        self._ready_event = threading.Event()

    def start(self):
        if self.is_started:
            return
        if not DOUBAO_APP_ID or not DOUBAO_ACCESS_TOKEN:
            raise ValueError("DOUBAO 配置缺失")
        self.is_started = True
        self._audio_count = 0
        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._ready_event.wait(timeout=3):
            self.is_started = False
            raise RuntimeError("ASR 初始化超时：内部队列未就绪")
        print(
            f"[ASR] Doubao 提供商已启动  ID={DOUBAO_APP_ID}  RID={DOUBAO_RESOURCE_ID}"
        )

    def _run(self):
        self._ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._ws_loop)
        self._audio_queue = asyncio.Queue()
        self._ready_event.set()
        try:
            self._ws_loop.run_until_complete(self._ws_client())
        except Exception as e:
            print(f"[ASR-Doubao] 循环异常: {e}")
        finally:
            self.is_started = False
            self._audio_queue = None
            if self._ws_loop and not self._ws_loop.is_closed():
                self._ws_loop.close()
            self._ws_loop = None

    async def _ws_client(self):
        self._recv_buffer = bytearray()
        # 豆包 V3 要求特殊的鉴权头
        headers = {
            "Authorization": f"Bearer;{DOUBAO_ACCESS_TOKEN}",
            "X-Api-App-Key": DOUBAO_APP_ID,
            "X-Api-Access-Key": DOUBAO_ACCESS_TOKEN,
            "X-Api-Resource-Id": DOUBAO_RESOURCE_ID,
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }
        # 有些文档提示 appid 需要在 URL 中
        ws_url = f"{self.BASE_URL}?appid={DOUBAO_APP_ID}"

        print(f"[ASR-Doubao] 正在发起 WebSocket 连接: {ws_url}")
        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                print("[ASR-Doubao] WebSocket 已建立连接")
                # 发送 init
                init_payload = {
                    "app": {
                        "appid": DOUBAO_APP_ID,
                        "token": DOUBAO_ACCESS_TOKEN,
                        "cluster": DOUBAO_CLUSTER,
                    },
                    "user": {"uid": str(uuid.uuid4())},
                    "audio": {
                        "format": "pcm",
                        "codec": "raw",
                        "rate": 16000,
                        "bits": 16,
                        "channel": 1,
                        "language": "zh-CN",
                    },
                    "request": {
                        "reqid": str(uuid.uuid4()),
                        "sequence": 1,
                        "show_utterances": True,
                        "result_type": "stream",
                        "vad_signal": True,
                        "workflow": "audio_in,resample,partition,vad,fe,decode",
                    },
                }
                await ws.send(self._build_full_client_frame(init_payload))
                print("[ASR-Doubao] Init 帧已发送")

                # 设置回调处理
                tasks = [
                    asyncio.create_task(self._sender(ws)),
                    asyncio.create_task(self._receiver(ws)),
                ]
                # 等待任意一个任务结束（或出错）
                done, pending = await asyncio.wait(
                    tasks, return_when=asyncio.FIRST_COMPLETED
                )
                for task in pending:
                    task.cancel()
                for task in done:
                    if task.exception():
                        print(f"[ASR-Doubao] 任务抛出异常: {task.exception()}")
        except Exception as e:
            print(f"[ASR-Doubao] WebSocket 异常: {e}")

    def _build_full_client_frame(self, p: dict) -> bytes:
        payload = json.dumps(p).encode("utf-8")
        # 构造 4 字节 Header: self.HEADER_VERSION_SIZE (\x11) + self.HEADER_FULL_CLIENT (\x10\x10\x00)
        header = self.HEADER_VERSION_SIZE + self.HEADER_FULL_CLIENT
        return header + struct.pack(">I", len(payload)) + payload

    def _build_audio_frame(self, b: bytes, last=False) -> bytes:
        h = self.HEADER_VERSION_SIZE + (
            self.HEADER_AUDIO_LAST if last else self.HEADER_AUDIO
        )
        return h + struct.pack(">I", len(b)) + b

    async def _sender(self, ws):
        while self.is_started:
            try:
                # 显式使用 wait_for 增加健壮性
                chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=1.0)
                if chunk is None:
                    await ws.send(self._build_audio_frame(b"", True))
                    break
                await ws.send(self._build_audio_frame(chunk))
                self._audio_count += 1
                if self._audio_count % 50 == 0:
                    print(f"[ASR-Doubao] 已发送 {self._audio_count} 帧音频")
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"[ASR-Doubao] 发送失败: {e}")
                break

    async def _receiver(self, ws):
        try:
            async for raw in ws:
                print(f"[ASR-Doubao] 收到原始数据 {len(raw)}B: {raw[:16].hex()}")
                if not isinstance(raw, bytes):
                    continue
                self._recv_buffer.extend(raw)
                while len(self._recv_buffer) >= 12:
                    if not self._recv_buffer.startswith(self.HEADER_VERSION_SIZE):
                        idx = self._recv_buffer.find(self.HEADER_VERSION_SIZE, 1)
                        if idx != -1:
                            self._recv_buffer = self._recv_buffer[idx:]
                            if len(self._recv_buffer) < 12:
                                break
                        else:
                            self._recv_buffer.clear()
                            break
                    # 响应帧格式: [4B 头][4B 序列号/状态][4B 长度][payload]
                    size = struct.unpack(">I", self._recv_buffer[8:12])[0]
                    if len(self._recv_buffer) < 12 + size:
                        break
                    packet = self._recv_buffer[: 12 + size]
                    payload_bytes = packet[12:]
                    self._recv_buffer = self._recv_buffer[12 + size :]
                    if not payload_bytes:
                        continue
                    try:
                        if (
                            payload_bytes.startswith(b"\x00\x00")
                            and len(payload_bytes) > 4
                        ):
                            json_str = payload_bytes[4:].decode("utf-8")
                        else:
                            json_str = payload_bytes.decode("utf-8")
                        data = json.loads(json_str)
                        # 调试日志：记录服务端返回的所有数据
                        if not data.get("result", {}).get("text"):
                            print(f"[ASR-Doubao] 服务端状态/消息: {data}")
                        else:
                            print(
                                f"[ASR-Doubao] 识别结果 (中间): {data['result']['text']}"
                            )
                    except Exception as e:
                        print(f"[ASR-Doubao] 解析异常: {e}, 长度: {len(packet)}")
                        continue
                    res = data.get("result", {}) or {}
                    text = res.get("text", "")
                    end = bool(res.get("definite") or res.get("is_final"))
                    if text:
                        if self.on_text_update and self.loop:
                            asyncio.run_coroutine_threadsafe(
                                self.on_text_update(text, end), self.loop
                            )
                    else:
                        if "error" in data or "err_msg" in data:
                            print(f"[ASR-Doubao] 服务端报错: {data}")
                        elif "resp" in data and isinstance(data["resp"], dict):
                            err = data["resp"].get("error_msg")
                            if err:
                                print(f"[ASR-Doubao] 逻辑报错: {err}")
        except websockets.exceptions.ConnectionClosed as e:
            print(f"[ASR-Doubao] 连接正常关闭或异常断开: {e}")
        except Exception as e:
            print(f"[ASR-Doubao] 接收协程异常: {e}")

    def add_audio(self, chunk: bytes):
        if (
            self.is_started
            and self._ws_loop
            and self._audio_queue is not None
            and not self._ws_loop.is_closed()
        ):
            asyncio.run_coroutine_threadsafe(
                self._audio_queue.put(chunk), self._ws_loop
            )

    def stop(self):
        self.is_started = False
        if (
            self._ws_loop
            and self._audio_queue is not None
            and not self._ws_loop.is_closed()
        ):
            asyncio.run_coroutine_threadsafe(self._audio_queue.put(None), self._ws_loop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)


class AliyunProvider(ASRProvider):
    """阿里云 (DashScope/Paraformer) 实现"""

    def __init__(self):
        super().__init__()
        import dashscope
        from dashscope.audio.asr import Recognition

        self.Recognition = Recognition
        self.recognition = None
        self.api_key = os.getenv("DASHSCOPE_API_KEY")

    def start(self):
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 缺失")
        import dashscope

        dashscope.api_key = self.api_key

        from dashscope.audio.asr import RecognitionCallback, RecognitionResult

        class LocalCallback(RecognitionCallback):
            def __init__(self, outer):
                super().__init__()
                self.outer = outer

            def on_event(self, res: RecognitionResult):
                text = (
                    res.get_sentence().get("text", "")
                    if isinstance(res.get_sentence(), dict)
                    else str(res.get_sentence())
                )
                if text and self.outer.on_text_update and self.outer.loop:
                    asyncio.run_coroutine_threadsafe(
                        self.outer.on_text_update(text, res.is_sentence_end()),
                        self.outer.loop,
                    )

            def on_error(self, res):
                print(f"[ASR-Ali] ERR: {res}")

            def on_close(self):
                print("[ASR-Ali] Closed")

        self.recognition = self.Recognition(
            model="paraformer-realtime-v2",
            format="pcm",
            sample_rate=16000,
            callback=LocalCallback(self),
        )
        self.recognition.start()
        self.is_started = True
        print("[ASR] Aliyun 提供商已启动")

    def add_audio(self, chunk: bytes):
        if self.is_started and self.recognition:
            self.recognition.send_audio_frame(chunk)

    def stop(self):
        if self.is_started and self.recognition:
            self.recognition.stop()
            self.is_started = False


# ── 工厂实例化 ──
def get_asr_processor() -> ASRProvider:
    if PROVIDER == "aliyun":
        return AliyunProvider()
    return DoubaoProvider()


asr_processor = get_asr_processor()
