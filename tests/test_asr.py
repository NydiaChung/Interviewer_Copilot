import pytest
import struct
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock
from server.asr import DoubaoProvider


# 模拟异步迭代器，用于模拟 WebSocket 接收数据
async def async_iter(data_list):
    for item in data_list:
        yield item


def test_doubao_build_full_client_frame():
    provider = DoubaoProvider()
    payload = {"test": "data"}
    frame = provider._build_full_client_frame(payload)

    # 验证长度: 4 (Header) + 4 (Length) + len(payload)
    payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    assert len(frame) == 8 + len(payload_json)

    # 验证 Header (V3 协议头 0x11101000)
    assert frame.startswith(b"\x11\x10\x10\x00")

    # 验证长度字段 (客户端发送使用 8 字节头，长度在 [4:8])
    length = struct.unpack(">I", frame[4:8])[0]
    assert length == len(payload_json)


def test_doubao_build_audio_frame():
    provider = DoubaoProvider()
    data = b"audio_data"

    # 普通音频帧
    frame = provider._build_audio_frame(data, last=False)
    assert frame.startswith(b"\x11\x20\x00\x00")
    length = struct.unpack(">I", frame[4:8])[0]
    assert length == len(data)

    # 结束帧
    last_frame = provider._build_audio_frame(data, last=True)
    assert last_frame.startswith(b"\x11\x22\x00\x00")


@pytest.mark.asyncio
async def test_doubao_receiver_buffer_recomposition():
    provider = DoubaoProvider()
    if not hasattr(provider, "_recv_buffer"):
        provider._recv_buffer = bytearray()

    # Fix 1: 豆包 V3 句末标志在 utterances[].definite，而非顶层 is_final
    message = {
        "result": {
            "text": "你好",
            "utterances": [{"text": "你好", "definite": True}],
        }
    }
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")

    # 构造包：4B协议头 + 4B序列号(0) + 4B长度 + Payload
    full_packet = (
        b"\x11\x10\x11\x00"
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(payload))
        + payload
    )

    # 故意将包拆分为极细码的帧
    chunks = [full_packet[i : i + 1] for i in range(len(full_packet))]

    processed_results = []

    async def mock_callback(text, end):
        processed_results.append((text, end))

    provider.on_text_update = mock_callback
    provider.loop = asyncio.get_running_loop()

    # 使用 MagicMock 配合异步生成器
    mock_ws = MagicMock()
    mock_ws.__aiter__.side_effect = lambda: async_iter(chunks)

    # 启动接收器
    await provider._receiver(mock_ws)

    # 给异步任务一点时间运行
    await asyncio.sleep(0.1)

    # 验证结果: text 正确， is_sentence_end=True
    assert len(processed_results) == 1
    assert processed_results[0][0] == "你好"
    assert (
        processed_results[0][1] is True
    )  # Fix 1: utterances[].definite=True 应被正确解析
    # 验证缓冲区已清空
    assert len(provider._recv_buffer) == 0


@pytest.mark.asyncio
async def test_doubao_receiver_no_utterances_defaults_to_false():
    """Fix 1: 当 utterances 为空时， is_sentence_end 应为 False。"""
    provider = DoubaoProvider()
    if not hasattr(provider, "_recv_buffer"):
        provider._recv_buffer = bytearray()

    # 不含 utterances，也不含 is_final
    message = {"result": {"text": "测试"}}
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    full_packet = (
        b"\x11\x10\x11\x00"
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(payload))
        + payload
    )

    processed_results = []

    async def mock_callback(text, end):
        processed_results.append((text, end))

    provider.on_text_update = mock_callback
    provider.loop = asyncio.get_running_loop()
    mock_ws = MagicMock()
    mock_ws.__aiter__.side_effect = lambda: async_iter([full_packet])
    await provider._receiver(mock_ws)
    await asyncio.sleep(0.1)

    assert len(processed_results) == 1
    assert processed_results[0][0] == "测试"
    assert processed_results[0][1] is False  # 没有 definite=True，应为 False


@pytest.mark.asyncio
async def test_doubao_receiver_error_handling():
    provider = DoubaoProvider()
    if not hasattr(provider, "_recv_buffer"):
        provider._recv_buffer = bytearray()

    # 模拟一个错误负载
    err_msg = {"error": "Invalid format", "err_msg": "test error"}
    payload = json.dumps(err_msg, ensure_ascii=False).encode("utf-8")

    # 构造 12 字节头回包
    full_packet = (
        b"\x11\x10\x11\x00"
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(payload))
        + payload
    )

    mock_ws = MagicMock()
    mock_ws.__aiter__.side_effect = lambda: async_iter([full_packet])

    # 只要不抛出未捕获异常即视为成功
    await provider._receiver(mock_ws)
    assert len(provider._recv_buffer) == 0


# --------------- Supplementary ASR Coverage ---------------


def test_asr_provider_base():
    from server.asr import ASRProvider

    class Concrete(ASRProvider):
        def start(self):
            super().start()

        def add_audio(self, c):
            super().add_audio(c)

        def stop(self):
            super().stop()

    p = Concrete()
    p.set_callback(lambda x, y: None, None)
    assert p.on_text_update is not None

    # abstract methods don't do anything but we call them for coverage
    p.start()
    p.add_audio(b"")
    p.stop()


def test_doubao_start_missing_keys(mocker):
    mocker.patch("server.asr.doubao.DOUBAO_APP_ID", "")
    p = DoubaoProvider()
    with pytest.raises(ValueError, match="DOUBAO"):
        p.start()


def test_doubao_start_timeout(mocker):
    mocker.patch("server.asr.doubao.DOUBAO_APP_ID", "test")
    mocker.patch("server.asr.doubao.DOUBAO_ACCESS_TOKEN", "test")
    p = DoubaoProvider()
    # mock event wait to always timeout
    mocker.patch.object(p._ready_event, "wait", return_value=False)
    with pytest.raises(RuntimeError, match="内部队列未就绪"):
        p.start()


def test_doubao_start_success_and_stop(mocker):
    mocker.patch("server.asr.doubao.DOUBAO_APP_ID", "test")
    mocker.patch("server.asr.doubao.DOUBAO_ACCESS_TOKEN", "test")
    p = DoubaoProvider()

    # Mock thread start to just immediately set ready event so it doesn't hang
    def fake_start():
        p._ready_event.set()
        p._ws_loop = MagicMock()
        p._audio_queue = MagicMock()

    mocker.patch("threading.Thread.start", side_effect=fake_start)
    p.start()
    assert p.is_started is True

    # Already started
    p.start()

    # Add audio
    p.add_audio(b"123")

    # Stop
    p.stop()
    assert p.is_started is False
    p.stop()  # call again


@pytest.mark.asyncio
async def test_doubao_sender_loop(mocker):
    p = DoubaoProvider()
    p.is_started = True
    p._audio_count = 0
    p._audio_queue = asyncio.Queue()

    await p._audio_queue.put(b"chunk1")
    await p._audio_queue.put(b"chunk2")
    await p._audio_queue.put(None)  # stop signal

    mock_ws = AsyncMock()
    await p._sender(mock_ws)
    assert mock_ws.send.call_count == 3

    # test sender timeout and exception
    p.is_started = True
    p._audio_queue = (
        asyncio.Queue()
    )  # empty queue will timeout eventually, but wait_for is mocked
    mocker.patch("asyncio.wait_for", side_effect=asyncio.TimeoutError)

    mock_ws.send.side_effect = Exception("err")
    await p._sender(mock_ws)


@pytest.mark.asyncio
async def test_doubao_ws_client_error(mocker):
    p = DoubaoProvider()
    mocker.patch("websockets.connect", side_effect=Exception("conn err"))
    await p._ws_client()


def test_doubao_run_wrapper(mocker):
    p = DoubaoProvider()
    mocker.patch.object(p, "_ws_client", side_effect=Exception("run err"))
    p._run()


from server.asr import TingwuProvider


def test_tingwu_start_missing_keys(mocker):
    mocker.patch("server.asr.tingwu.ALIYUN_AK_ID", "")
    p = TingwuProvider()
    with pytest.raises(ValueError):
        p.start()


def test_tingwu_start_missing_keys():
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {}, clear=True):
        p = TingwuProvider()
        with pytest.raises(ValueError):
            p.start()


def test_tingwu_start_success_stop_add_audio(mocker):
    import os
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {
            "TINGWU_ACCESS_KEY_ID": "a",
            "TINGWU_ACCESS_KEY_SECRET": "b",
            "TINGWU_APP_KEY": "c",
        },
    ):
        p = TingwuProvider()

        mocker.patch.object(
            p, "_create_realtime_task", return_value=("task_123", "wss://url")
        )

        # mock thread start
        def fake_start():
            p._ready_event.set()

        mocker.patch("threading.Thread.start", side_effect=fake_start)

        p.start()
        assert p.is_started is True

        # send audio
        p.add_audio(b"pcm")

        # stop
        mocker.patch.object(p, "_stop_realtime_task")
        p.stop()
        assert p.is_started is False

        # call stop again
        p.stop()


def test_tingwu_create_and_stop_task(mocker):
    import os
    from unittest.mock import patch

    with patch.dict(
        os.environ,
        {
            "TINGWU_ACCESS_KEY_ID": "a",
            "TINGWU_ACCESS_KEY_SECRET": "b",
            "TINGWU_APP_KEY": "c",
        },
    ):
        p = TingwuProvider()

        mock_client = MagicMock()
        mock_client.do_action_with_exception.return_value = json.dumps(
            {"Data": {"TaskId": "123", "MeetingJoinUrl": "ws"}}
        ).encode()
        mocker.patch("aliyunsdkcore.client.AcsClient", return_value=mock_client)

        tid, url = p._create_realtime_task()
        assert tid == "123"
        assert url == "ws"

        # test failure
        mock_client.do_action_with_exception.return_value = json.dumps(
            {"Data": {}}
        ).encode()
        with pytest.raises(RuntimeError):
            p._create_realtime_task()

        # test stop
        p._task_id = "123"
        mock_client.do_action_with_exception.return_value = b'{"success": true}'
        p._stop_realtime_task()


def test_tingwu_callbacks():
    p = TingwuProvider()
    p.on_text_update = AsyncMock()
    p.loop = asyncio.new_event_loop()

    # start
    p._on_start("msg")
    assert p._ready_event.is_set()

    # phrase begin — now takes dict, not JSON string
    p._on_sentence_begin(
        {"payload": {"speaker_id": "spk1", "speaker_name": "Speaker1"}}
    )
    assert p.last_speaker_id == "spk1"
    assert p.last_speaker_name == "Speaker1"

    # result changed
    p._on_result_changed({"payload": {"result": "txt"}})

    # sentence end
    p._on_sentence_end({"payload": {"result": "txt"}})

    # completed
    p._on_completed("msg")

    # error
    p._on_error("err")
