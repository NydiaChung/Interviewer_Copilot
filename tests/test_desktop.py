import os
import json
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

# --- Test UserSettingsDialog ---
# 既然 UserSettingsDialog 有静态方法读取路径下的 settings.json，我们通过 patch 模拟文件操作
from desktop_app.user_settings_dialog import UserSettingsDialog


def test_user_settings_load_save(tmp_path):
    # 为测试创建一个临时配置文件
    test_settings_file = tmp_path / "settings.json"
    data = {"resume": "My Resume Text", "extra_info": "Extra Info"}

    with open(test_settings_file, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # Patch UserSettingsDialog 的 settings_path
    # 静态方法 _load 内部硬编码了相对路径，我们直接 patch 它使用的 open
    with patch(
        "builtins.open", MagicMock(side_effect=open)
    ):  # 这里比较Trick，我们直接 patch path 逻辑
        with patch("os.path.exists", return_value=True):
            with patch(
                "builtins.open",
                MagicMock(return_value=open(test_settings_file, "r", encoding="utf-8")),
            ):
                loaded = UserSettingsDialog._load()
                assert loaded["resume"] == "My Resume Text"
                assert loaded["extra_info"] == "Extra Info"


def test_user_settings_get_helpers():
    # 测试静态便捷方法
    with patch.object(
        UserSettingsDialog, "_load", return_value={"resume": "R", "extra_info": "E"}
    ):
        assert UserSettingsDialog.get_default_resume() == "R"
        assert UserSettingsDialog.get_extra_info() == "E"


# --- Test AudioCapture Resampling Logic ---
from desktop_app.audio_capture import AudioCapture


def test_audio_capture_resampling_logic():
    # 模拟 callback
    mock_cb = MagicMock()

    # 模拟 PyAudio 初始化 (防止在单测环境因为没声卡崩溃)
    with patch("pyaudio.PyAudio"):
        # 强制 PYAUDIO_OK 为 True
        with patch("desktop_app.audio_capture.PYAUDIO_OK", True):
            with patch(
                "desktop_app.audio_capture._find_devices", return_value=(0, 1, 2, 48000)
            ):
                ac = AudioCapture(mock_cb)
                ac.sys_stream = object()

                # 为重采样准备一段 48kHz 的双声道模拟数据 (静音数据)
                # 假设采样率是 48000, 2通道, 16bit = 4字节每样本帧
                # 传入 1 帧数据 (4字节)
                raw_audio = b"\x00\x00\x00\x00" * 480
                # 480 帧双声道数据 = 1920 字节

                # 测试 _sys_to_16k_mono
                # 48000Hz -> 16000Hz 应该是 3:1 采样率
                resampled = ac._sys_to_16k_mono(raw_audio)

                # 480 帧 48k 输入 -> 应产生 160 帧 16k 输出
                # 每帧 2 字节（单声道 int16）
                assert len(resampled) == 160 * 2

                # 再次调用，验证状态连续性 (state 不应为 None)
                assert ac._ratecv_state is not None
                resampled2 = ac._sys_to_16k_mono(raw_audio)
                assert len(resampled2) == 160 * 2


def test_audio_capture_mixing_logic():
    mock_cb = MagicMock()
    with patch("pyaudio.PyAudio"):
        with patch("desktop_app.audio_capture.PYAUDIO_OK", True):
            with patch(
                "desktop_app.audio_capture._find_devices",
                return_value=(0, None, 1, 16000),
            ):
                ac = AudioCapture(mock_cb)
                ac.mic_stream = object()

                # 仅开启麦克风的情况下 (system_index 为 None)
                # CHUNK_16K = 3200 帧, N = 6400 字节
                data = b"\x01" * 6400
                ac.mic_buffer = data
                ac._send_audio()

                mock_cb.assert_called_once_with(data)
                assert len(ac.mic_buffer) == 0


def test_audio_capture_system_only_fallback():
    mock_cb = MagicMock()
    with patch("pyaudio.PyAudio"):
        with patch("desktop_app.audio_capture.PYAUDIO_OK", True):
            with patch(
                "desktop_app.audio_capture._find_devices",
                return_value=(None, 1, 2, 48000),
            ):
                ac = AudioCapture(mock_cb)
                ac.sys_stream = object()
                data = b"\x02" * 6400
                ac.sys_buffer = data
                ac._send_audio()

                mock_cb.assert_called_once_with(data)
                assert len(ac.sys_buffer) == 0


def test_audio_capture_dual_stream_fallback_routes_mic_to_main_when_no_system_device():
    mock_cb = MagicMock()
    with patch("pyaudio.PyAudio"):
        with patch("desktop_app.audio_capture.PYAUDIO_OK", True):
            # 无 system 设备：双流应自动降级为 mic -> system(main)
            with patch(
                "desktop_app.audio_capture._find_devices",
                return_value=(0, None, 1, 16000),
            ):
                ac = AudioCapture(mock_cb, dual_stream_mode=True)
                ac.mic_stream = object()
                data = b"\x03" * 6400
                ac.mic_buffer = data
                ac._send_audio()

                mock_cb.assert_called_once_with(data, channel="system")
                assert len(ac.mic_buffer) == 0
