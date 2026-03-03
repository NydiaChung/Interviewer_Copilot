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

    # 模拟一个完整的回包: [4B头] + [4B序列号] + [4B长度] + [JSON]
    # 豆包 V3 服务端回包是 12 字节头
    message = {"result": {"text": "你好", "is_final": True}}
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")

    # 构造包：4B协议头 + 4B序列号(0) + 4B长度 + Payload
    full_packet = (
        b"\x11\x10\x11\x00"
        + b"\x00\x00\x00\x00"
        + struct.pack(">I", len(payload))
        + payload
    )

    # 故意将包拆分为极细碎的帧
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

    # 验证结果
    assert len(processed_results) == 1
    assert processed_results[0][0] == "你好"
    assert processed_results[0][1] is True
    # 验证缓冲区已清空
    assert len(provider._recv_buffer) == 0


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
