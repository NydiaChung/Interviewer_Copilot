"""通义听悟（阿里云）实时 ASR 实现 —— 支持说话人分离。"""

import asyncio
import json
import os
import threading
import uuid

from server.asr.base import ASRProvider

# 阿里云配置
ALIYUN_AK_ID = os.getenv("TINGWU_ACCESS_KEY_ID", "")
ALIYUN_AK_SECRET = os.getenv("TINGWU_ACCESS_KEY_SECRET", "")
ALI_APP_KEY = os.getenv("TINGWU_APP_KEY", "")


class TingwuProvider(ASRProvider):
    """通义听悟实时 ASR —— REST CreateTask + WebSocket 推流。"""

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
        self._ws = None
        self._ws_loop = None
        self._thread = None
        self._ready_event = threading.Event()
        self.last_speaker_id = None
        self.last_speaker_name = None

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def start(self):
        if self.is_started:
            return
        if not self._ak_id or not self._ak_secret or not self._app_key:
            raise ValueError(
                "TINGWU 配置缺失 "
                "(TINGWU_ACCESS_KEY_ID / TINGWU_ACCESS_KEY_SECRET / TINGWU_APP_KEY)"
            )

        self._task_id, self._meeting_url = self._create_realtime_task()
        print(f"[ASR-Tingwu] TaskId={self._task_id}")
        print(f"[ASR-Tingwu] MeetingJoinUrl={self._meeting_url[:80]}...")

        self._ready_event.clear()
        self._thread = threading.Thread(target=self._run_nls, daemon=True)
        self._thread.start()

        if not self._ready_event.wait(timeout=10):
            raise RuntimeError("ASR-Tingwu 推流建立超时")

        self.is_started = True
        print(
            f"[ASR] 通义听悟提供商已启动 (说话人分离={self._speaker_count}人)"
        )

    def add_audio(self, chunk: bytes):
        if self.is_started and self._ws:
            try:
                loop = self._ws_loop
                if not loop:
                    return
                future = asyncio.run_coroutine_threadsafe(
                    self._ws.send(chunk), loop
                )

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

        if self._ws:
            try:
                loop = self._ws_loop
                if loop and not loop.is_closed():
                    asyncio.run_coroutine_threadsafe(self._ws.close(), loop)
            except Exception as e:
                print(f"[ASR-Tingwu] WebSocket close 异常: {e}")

        self._stop_realtime_task()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    # ------------------------------------------------------------------
    # REST API
    # ------------------------------------------------------------------

    def _create_realtime_task(self) -> tuple:
        """调用 CreateTask 创建实时记录任务。"""
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
                    "OutputLevel": 2,
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
        print(
            f"[ASR-Tingwu] CreateTask 响应: "
            f"{json.dumps(resp, ensure_ascii=False)}"
        )

        data = resp.get("Data", {})
        task_id = data.get("TaskId", "")
        meeting_url = data.get("MeetingJoinUrl", "")
        if not task_id or not meeting_url:
            raise RuntimeError(f"CreateTask 失败: {resp}")
        return task_id, meeting_url

    def _stop_realtime_task(self):
        """调用 REST API 结束实时记录。"""
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

    # ------------------------------------------------------------------
    # WebSocket 推流线程
    # ------------------------------------------------------------------

    def _run_nls(self):
        """在独立线程中运行 WebSocket 推流。"""
        import websockets as ws_lib

        async def _async_run():
            try:
                async with ws_lib.connect(self._meeting_url) as ws:
                    self._ws = ws

                    start_cmd = {
                        "header": {
                            "message_id": uuid.uuid4().hex,
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

                    async for message in ws:
                        if not self.is_started:
                            break
                        self._dispatch_event(message)
            except Exception as e:
                print(f"[ASR-Tingwu] WebSocket 连接断开/异常: {e}")
                self._ready_event.set()

        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        self._ws_loop = new_loop
        try:
            new_loop.run_until_complete(_async_run())
        finally:
            self._ws_loop = None
            new_loop.close()

    # ------------------------------------------------------------------
    # 事件分发
    # ------------------------------------------------------------------

    def _dispatch_event(self, message: str):
        """根据事件 name 分发到对应处理方法。"""
        try:
            data = json.loads(message)
            header = data.get("header", {})
            name = header.get("name")

            if name == "TranscriptionStarted":
                self._on_start(message)
            elif name == "SentenceBegin":
                self._on_sentence_begin(data)
            elif name == "TranscriptionResultChanged":
                self._on_result_changed(data)
            elif name == "SentenceEnd":
                self._on_sentence_end(data)
            elif name == "TaskFailed":
                self._on_error(message)
            elif name == "TranscriptionCompleted":
                self._on_completed(message)
        except Exception as e:
            print(f"[ASR-Tingwu] 解析回调异常: {e}")

    def _extract_speaker_info(self, payload: dict):
        """从 payload 提取说话人信息并更新状态。"""
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
        return speaker, speaker_name

    def _fire_callback(self, text: str, is_end: bool):
        """线程安全地触发文本回调。"""
        if text and self.on_text_update and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.on_text_update(text, is_end), self.loop
            )

    # ------------------------------------------------------------------
    # 回调处理
    # ------------------------------------------------------------------

    def _on_start(self, message):
        print(f"[ASR-Tingwu] 推流已建立: {message}")
        self._ready_event.set()

    def _on_sentence_begin(self, data: dict):
        payload = data.get("payload", {})
        speaker, speaker_name = self._extract_speaker_info(payload)
        print(
            f"[ASR-Tingwu] SentenceBegin: "
            f"index={payload.get('index')} speaker={speaker} name={speaker_name}"
        )

    def _on_result_changed(self, data: dict):
        """中间结果。"""
        payload = data.get("payload", {})
        text = payload.get("result", "")
        speaker, speaker_name = self._extract_speaker_info(payload)

        if text:
            print(
                f"[ASR-Tingwu] ResultChanged: {text} "
                f"(speaker={speaker}, name={speaker_name})"
            )
        self._fire_callback(text, False)

    def _on_sentence_end(self, data: dict):
        """句子结束。"""
        payload = data.get("payload", {})
        text = payload.get("result", "")
        speaker, speaker_name = self._extract_speaker_info(payload)

        stash = payload.get("stash_result", {})
        stash_text = stash.get("text", "") if stash else ""
        full_text = text + stash_text if stash_text else text

        print(
            f"[ASR-Tingwu] SentenceEnd: speaker={speaker} "
            f"name={speaker_name} text={text} stash={stash_text}"
        )
        self._fire_callback(full_text, True)

    def _on_completed(self, message):
        print(f"[ASR-Tingwu] 识别完成: {message}")

    def _on_error(self, message):
        print(f"[ASR-Tingwu] 错误: {message}")
