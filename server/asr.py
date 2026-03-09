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
PROVIDER = os.getenv("ASR_PROVIDER", "tingwu").lower()

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


# === 基于豆包（ByteDance）的 ASR 实现 ===
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
                # Fix: 增加心跳/闲置补偿逻辑。
                # 如果超过 1 秒没有音频进入队列，主动发送一个长度为 0 的音频帧，
                # 告知服务端连接仍然活跃，防止触发 "waiting next packet timeout" 错误。
                try:
                    await ws.send(self._build_audio_frame(b"", last=False))
                except Exception as e:
                    print(f"[ASR-Doubao] 发送心跳帧失败: {e}")
                    break
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
                    # Fix 1 修正: 豆包累积 utterances 中历史句子 definite 永远为 True。
                    # 只检查「最后一个 utterance」的 definite，它代表当前最新捕捉到的句子
                    # 是否已由 ASR 确认（不再可能被撤回修改）。
                    utterances = res.get("utterances") or []
                    if utterances:
                        # 最后一个 utterance 的 definite 代表当前句子是否结束
                        end = bool(utterances[-1].get("definite")) or bool(
                            res.get("is_final")
                        )
                    else:
                        end = bool(res.get("is_final"))

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


class TingwuProvider(ASRProvider):
    """通义听悟（阿里云）实时 ASR 实现 —— 支持说话人分离

    生命周期：
      1. start()  → REST CreateTask 获取 MeetingJoinUrl + NLS SDK 建立推流
      2. add_audio() → 透传 PCM 给 NLS
      3. stop()  → NLS stop + REST 结束任务
    """

    TINGWU_ENDPOINT = "tingwu.cn-beijing.aliyuncs.com"
    TINGWU_API_VERSION = "2023-09-30"

    def __init__(self):
        super().__init__()
        self._ak_id = os.getenv("TINGWU_ACCESS_KEY_ID", "")
        self._ak_secret = os.getenv("TINGWU_ACCESS_KEY_SECRET", "")
        self._app_key = os.getenv("TINGWU_APP_KEY", "")
        self._speaker_count = int(os.getenv("TINGWU_SPEAKER_COUNT", "2"))
        self._task_id = None
        self._meeting_url = None
        self._rm = None  # NlsRealtimeMeeting 实例
        self._thread = None
        self._ready_event = threading.Event()
        self.last_speaker_id = None  # 最近一次识别到的说话人 ID

    # ── REST API 辅助 ──

    def _create_realtime_task(self) -> tuple:
        """调用 CreateTask 创建实时记录任务，返回 (task_id, meeting_join_url)"""
        from aliyunsdkcore.client import AcsClient
        from aliyunsdkcore.request import CommonRequest

        client = AcsClient(self._ak_id, self._ak_secret, "cn-beijing")
        request = CommonRequest()
        request.set_domain(self.TINGWU_ENDPOINT)
        request.set_version(self.TINGWU_API_VERSION)
        request.set_protocol_type("https")
        request.set_method("PUT")
        request.set_uri_pattern("/openapi/tingwu/v2/tasks")
        request.add_query_param("type", "realtime")
        request.set_content_type("application/json")

        body = {
            "AppKey": self._app_key,
            "Input": {
                "SourceLanguage": "cn",
                "Format": "pcm",
                "SampleRate": 16000,
                "TaskKey": f"interview_{uuid.uuid4().hex[:8]}",
            },
            "Parameters": {
                "Transcription": {
                    "OutputLevel": 2,  # 返回中间结果 + 完整句子
                    "DiarizationEnabled": True,
                    "Diarization": {
                        "SpeakerCount": self._speaker_count,
                    },
                },
                "IdentityRecognitionEnabled": True,
                "IdentityRecognition": {
                    "SceneIntroduction": "这是一场在线技术面试",
                    "IdentityContents": [
                        {
                            "Name": "interviewer",
                            "Description": "面试官，负责提出面试问题和考察候选人",
                        },
                        {
                            "Name": "candidate",
                            "Description": "应聘者，负责回答面试官提出的问题",
                        },
                    ],
                },
            },
        }
        request.set_content(json.dumps(body).encode("utf-8"))

        response = client.do_action_with_exception(request)
        resp = json.loads(response)
        print(f"[ASR-Tingwu] CreateTask 响应: {json.dumps(resp, ensure_ascii=False)}")

        data = resp.get("Data", {})
        task_id = data.get("TaskId", "")
        meeting_url = data.get("MeetingJoinUrl", "")
        if not task_id or not meeting_url:
            raise RuntimeError(f"CreateTask 失败: {resp}")
        return task_id, meeting_url

    def _stop_realtime_task(self):
        """调用 CreateTask(operation=stop) 结束实时记录"""
        if not self._task_id:
            return
        try:
            from aliyunsdkcore.client import AcsClient
            from aliyunsdkcore.request import CommonRequest

            client = AcsClient(self._ak_id, self._ak_secret, "cn-beijing")
            request = CommonRequest()
            request.set_domain(self.TINGWU_ENDPOINT)
            request.set_version(self.TINGWU_API_VERSION)
            request.set_protocol_type("https")
            request.set_method("PUT")
            request.set_uri_pattern("/openapi/tingwu/v2/tasks")
            request.add_query_param("type", "realtime")
            request.add_query_param("operation", "stop")
            request.set_content_type("application/json")

            body = {"Input": {"TaskId": self._task_id}}
            request.set_content(json.dumps(body).encode("utf-8"))

            response = client.do_action_with_exception(request)
            print(f"[ASR-Tingwu] 任务已结束: {response.decode('utf-8')}")
        except Exception as e:
            print(f"[ASR-Tingwu] 结束任务异常: {e}")

    # ── NLS 回调 ──

    def _on_start(self, message, *args):
        print(f"[ASR-Tingwu] 推流已建立: {message}")
        self._ready_event.set()

    def _on_sentence_begin(self, message, *args):
        try:
            data = json.loads(message) if isinstance(message, str) else {}
            payload = data.get("payload", {})
            speaker = payload.get("speaker_id")
            speaker_name = (
                payload.get("speaker_name")
                or payload.get("identity")
                or payload.get("role")
            )
            if speaker is not None:
                self.last_speaker_id = str(speaker)
            if speaker_name:
                self.last_speaker_name = str(speaker_name)
            print(
                f"[ASR-Tingwu] SentenceBegin: index={payload.get('index')} speaker={speaker} name={speaker_name}"
            )
        except Exception:
            pass

    def _on_result_changed(self, message, *args):
        """中间结果 → on_text_update(text, False)"""
        try:
            data = json.loads(message) if isinstance(message, str) else {}
            payload = data.get("payload", {})
            text = payload.get("result", "")
            speaker = payload.get("speaker_id")
            speaker_name = (
                payload.get("speaker_name")
                or payload.get("identity")
                or payload.get("role")
            )
            if speaker is not None:
                self.last_speaker_id = str(speaker)
            if speaker_name:
                self.last_speaker_name = str(speaker_name)

            if text:
                print(
                    f"[ASR-Tingwu] ResultChanged: {text} (speaker={speaker}, name={speaker_name})"
                )
            if text and self.on_text_update and self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.on_text_update(text, False), self.loop
                )
        except Exception as e:
            print(f"[ASR-Tingwu] ResultChanged 解析异常: {e}")

    def _on_sentence_end(self, message, *args):
        """句子结束 → on_text_update(text, True)"""
        try:
            data = json.loads(message) if isinstance(message, str) else {}
            payload = data.get("payload", {})
            text = payload.get("result", "")
            speaker = payload.get("speaker_id")
            speaker_name = (
                payload.get("speaker_name")
                or payload.get("identity")
                or payload.get("role")
            )

            if speaker is not None:
                self.last_speaker_id = str(speaker)
            if speaker_name:
                self.last_speaker_name = str(speaker_name)

            # 拼接 stash_result（暂存的下一句开头）
            stash = payload.get("stash_result", {})
            stash_text = stash.get("text", "") if stash else ""

            full_text = text
            if stash_text:
                full_text = text + stash_text

            print(
                f"[ASR-Tingwu] SentenceEnd: speaker={speaker} name={speaker_name} text={text} stash={stash_text}"
            )
            print(f"DEBUG: Tingwu Final Text: {full_text}")

            if full_text and self.on_text_update and self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.on_text_update(full_text, True), self.loop
                )
        except Exception as e:
            print(f"[ASR-Tingwu] SentenceEnd 解析异常: {e}")

    def _on_completed(self, message, *args):
        print(f"[ASR-Tingwu] 识别完成: {message}")

    def _on_error(self, message, *args):
        print(f"[ASR-Tingwu] 错误: {message}")

    def _on_close(self, *args):
        print("[ASR-Tingwu] 连接关闭")

    # ── 主推流线程 ──

    def _run_nls(self):
        """在独立线程中运行 WebSocket 推流"""

        async def _async_run():
            import websockets

            try:
                # 听悟官方最新协议：连接建立后，需立即发送 StartTranscription 指令开始推流
                async with websockets.connect(self._meeting_url) as ws:
                    self._ws = ws

                    # 握手指令
                    start_msg_id = uuid.uuid4().hex
                    start_cmd = {
                        "header": {
                            "message_id": start_msg_id,
                            "task_id": self._task_id,
                            "namespace": "SpeechTranscriber",
                            "name": "StartTranscription",
                            "appkey": self._app_key,
                        },
                        "payload": {
                            "format": "pcm",
                            "sample_rate": 16000,
                            "enable_intermediate_result": True,
                        },
                    }
                    await ws.send(json.dumps(start_cmd))

                    self._ready_event.set()

                    # 循环接收云端回传事件
                    async for message in ws:
                        if not self.is_started:
                            break
                        try:
                            data = json.loads(message)
                            header = data.get("header", {})
                            name = header.get("name")

                            if name == "TranscriptionStarted":
                                self._on_start(message)
                            elif name == "SentenceBegin":
                                self._on_sentence_begin(message)
                            elif name == "TranscriptionResultChanged":
                                self._on_result_changed(message)
                            elif name == "SentenceEnd":
                                self._on_sentence_end(message)
                            elif name == "TaskFailed":
                                self._on_error(message)
                            elif name == "TranscriptionCompleted":
                                self._on_completed(message)
                                break
                        except Exception as e:
                            print(f"[ASR-Tingwu] 解析回调异常: {e}")
            except Exception as e:
                print(f"[ASR-Tingwu] WebSocket 连接断开/异常: {e}")
                self._ready_event.set()

        # 由于外层是一个普通的 Thread，我们需要起一个事件循环
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        self._ws_loop = new_loop
        try:
            new_loop.run_until_complete(_async_run())
        finally:
            self._ws_loop = None
            new_loop.close()

    # ── ASRProvider 接口实现 ──

    def start(self):
        if self.is_started:
            return
        if not self._ak_id or not self._ak_secret or not self._app_key:
            raise ValueError(
                "TINGWU 配置缺失 (TINGWU_ACCESS_KEY_ID / TINGWU_ACCESS_KEY_SECRET / TINGWU_APP_KEY)"
            )

        # 1. REST 创建任务
        self._task_id, self._meeting_url = self._create_realtime_task()
        print(f"[ASR-Tingwu] TaskId={self._task_id}")
        print(f"[ASR-Tingwu] MeetingJoinUrl={self._meeting_url[:80]}...")

        # 2. NLS 推流（在独立线程中）
        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run_nls, daemon=True)
        self._thread.start()

        if not self._ready_event.wait(timeout=10):
            raise RuntimeError("ASR-Tingwu 推流建立超时")

        self.is_started = True
        print(f"[ASR] 通义听悟提供商已启动 (说话人分离={self._speaker_count}人)")

    def add_audio(self, chunk: bytes):
        if self.is_started and hasattr(self, "_ws") and self._ws:
            try:
                # 必须将任务丢给自己所在的 WS 专门专用的 Event Loop (新建的 new_loop)
                loop = getattr(self, "_ws_loop", None)
                if not loop:
                    return
                # 包装发送音频（要按照阿里的 OP_BINARY 标准发送纯二进制即可，因为 Start 已经声明格式为 pcm）

                future = asyncio.run_coroutine_threadsafe(self._ws.send(chunk), loop)

                def _on_done(f):
                    try:
                        f.result()
                    except Exception as e:
                        print(f"[ASR-Tingwu] 跨线程发送 WS 音频失败: {e}")

                future.add_done_callback(_on_done)
            except Exception as e:
                print(f"[ASR-Tingwu] 发送音频排队失败: {e}")

    def stop(self):
        if not self.is_started:
            return
        self.is_started = False

        # 1. 停止 WebSocket 推流
        if hasattr(self, "_ws") and self._ws:
            try:
                loop = getattr(self, "_ws_loop", None)
                if loop and not loop.is_closed():
                    asyncio.run_coroutine_threadsafe(self._ws.close(), loop)
            except Exception as e:
                print(f"[ASR-Tingwu] WebSocket close 异常: {e}")

        # 2. REST 结束任务
        self._stop_realtime_task()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)


# ── 工厂实例化 ──
def get_asr_processor() -> ASRProvider:
    print(f"[ASR] 使用 {PROVIDER} ASR 提供商")
    if PROVIDER == "tingwu":
        return TingwuProvider()
    return DoubaoProvider()


asr_processor = get_asr_processor()
