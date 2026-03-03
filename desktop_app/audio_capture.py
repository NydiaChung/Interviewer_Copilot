"""
音频采集模块
- 麦克风：MacBook Pro 内置麦克风，16kHz 单声道
- 系统声音：BlackHole（优先 2ch/48kHz，次选 16ch/44100Hz）
  → 多声道混为单声道 → audioop.ratecv 精确重采样至 16kHz

音频路由说明：
  应在「音频 MIDI 设置」中创建「多输出设备」（主设备=扬声器 + BlackHole 2ch），
  并设为系统输出。此时 BlackHole 2ch INPUT 侧可读取到系统声音。
"""

import audioop
import numpy as np

CHUNK_16K = 3200  # 16kHz 每块帧数（≈200ms）
RATE_MIC = 16000  # 麦克风目标采样率
MAX_BUFFER_CHUNKS = 50  # 内存保护：每路最多保留约 10s 数据

try:
    import pyaudio

    FORMAT = pyaudio.paInt16
    PYAUDIO_OK = True
except Exception as e:
    print(f"[Audio] PyAudio 不可用: {e}")
    PYAUDIO_OK = False


def _find_devices(p):
    """遍历 PyAudio 设备列表，返回 (mic_index, system_index, bh_channels, bh_rate)"""
    mic_index = None
    system_index = None
    bh_channels = 2
    bh_rate = 48000

    # 遍历：优先选 BlackHole 2ch，次选 BlackHole 16ch
    bh2_idx = None
    bh16_idx = None

    for i in range(p.get_device_count()):
        dev = p.get_device_info_by_index(i)
        name = dev.get("name", "").lower()
        ch = dev.get("maxInputChannels", 0)
        rate = int(dev.get("defaultSampleRate", 48000))
        if ch <= 0:
            continue

        if "blackhole 2ch" in name:
            bh2_idx = i
        elif "blackhole 16ch" in name:
            bh16_idx = i

        # 内置麦克风（兼容中/英文系统名称）
        is_mac_mic = "macbook pro" in name and ("mic" in name or "麦克风" in name)
        if is_mac_mic and mic_index is None:
            mic_index = i
            print(f"[Audio] 麦克风   → #{i}: {dev['name']}")

    # 选 BlackHole 设备：2ch 优先
    if bh2_idx is not None:
        system_index = bh2_idx
        dev = p.get_device_info_by_index(bh2_idx)
        bh_channels = min(int(dev.get("maxInputChannels", 2)), 2)
        bh_rate = int(dev.get("defaultSampleRate", 48000))
    elif bh16_idx is not None:
        system_index = bh16_idx
        dev = p.get_device_info_by_index(bh16_idx)
        bh_channels = min(int(dev.get("maxInputChannels", 16)), 16)
        bh_rate = int(dev.get("defaultSampleRate", 44100))

    if system_index is not None:
        dev = p.get_device_info_by_index(system_index)
        print(
            f"[Audio] 系统声音 → #{system_index}: {dev['name']}  ch={bh_channels}  rate={bh_rate}"
        )

    # 麦克风回退：第一个非 BlackHole 输入设备
    if mic_index is None:
        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            name = dev.get("name", "").lower()
            if dev.get("maxInputChannels", 0) > 0 and "blackhole" not in name:
                mic_index = i
                print(f"[Audio] 麦克风回退 → #{i}: {dev['name']}")
                break

    return mic_index, system_index, bh_channels, bh_rate


class AudioCapture:
    def __init__(self, callback):
        if not PYAUDIO_OK:
            raise RuntimeError("PyAudio 未安装")
        self.p = pyaudio.PyAudio()
        self.callback = callback
        self.is_running = False
        self.mic_buffer = b""
        self.sys_buffer = b""
        self._ratecv_state = None  # audioop.ratecv 状态（保持率转换连续性）

        self.mic_index, self.system_index, self.bh_channels, self.bh_rate = (
            _find_devices(self.p)
        )
        # 每块对应 BlackHole 原始帧数（向上取整保证不丢数据）
        self.bh_chunk = max(CHUNK_16K, int(CHUNK_16K * self.bh_rate / RATE_MIC))
        self.mic_stream = None
        self.sys_stream = None

    def start(self):
        self.is_running = True

        # ── 麦克风（16kHz 单声道）──
        if self.mic_index is not None:
            try:
                self.mic_stream = self.p.open(
                    format=FORMAT,
                    channels=1,
                    rate=RATE_MIC,
                    input=True,
                    input_device_index=self.mic_index,
                    frames_per_buffer=CHUNK_16K,
                    stream_callback=self._mic_callback,
                )
                self.mic_stream.start_stream()
                print("[Audio] 麦克风流已开启（16kHz）")
            except Exception as e:
                print(f"[Audio] 麦克风流失败: {e}")
                self.mic_stream = None

        # ── BlackHole（动态参数，audioop.ratecv 精确重采样）──
        if self.system_index is not None:
            try:
                self.sys_stream = self.p.open(
                    format=FORMAT,
                    channels=self.bh_channels,
                    rate=self.bh_rate,
                    input=True,
                    input_device_index=self.system_index,
                    frames_per_buffer=self.bh_chunk,
                    stream_callback=self._sys_callback,
                )
                self.sys_stream.start_stream()
                print(
                    f"[Audio] BlackHole 流已开启  ch={self.bh_channels}  "
                    f"{self.bh_rate}Hz→{RATE_MIC}Hz  (audioop.ratecv)"
                )
            except Exception as e:
                print(f"[Audio] BlackHole 流失败: {e}")
                self.sys_stream = None

    def _sys_to_16k_mono(self, raw: bytes) -> bytes:
        """多声道 + 任意采样率 → 16kHz 单声道（精确重采样）"""
        ch = self.bh_channels
        # 1. 多声道 → 单声道（各声道平均）
        data = np.frombuffer(raw, dtype=np.int16).reshape(-1, ch)
        mono = data.mean(axis=1).astype(np.int16).tobytes()
        # 2. 任意采样率 → 16kHz（audioop.ratecv 保持连续状态，不引入断续噪声）
        mono_16k, self._ratecv_state = audioop.ratecv(
            mono, 2, 1, self.bh_rate, RATE_MIC, self._ratecv_state
        )
        return mono_16k

    def _mix_and_send(self):
        N = CHUNK_16K * 2  # 字节数（int16 = 2 bytes/sample）
        has_mic = self.mic_stream is not None
        has_sys = self.sys_stream is not None

        if has_mic and has_sys:
            while len(self.mic_buffer) >= N and len(self.sys_buffer) >= N:
                mic_chunk = self.mic_buffer[:N]
                self.mic_buffer = self.mic_buffer[N:]
                sys_chunk = self.sys_buffer[:N]
                self.sys_buffer = self.sys_buffer[N:]
                mic_np = np.frombuffer(mic_chunk, dtype=np.int16).astype(np.int32)
                sys_np = np.frombuffer(sys_chunk, dtype=np.int16).astype(np.int32)
                mixed = np.clip(mic_np + sys_np, -32768, 32767).astype(np.int16)
                self.callback(mixed.tobytes())
            return

        if has_mic:
            while len(self.mic_buffer) >= N:
                chunk = self.mic_buffer[:N]
                self.mic_buffer = self.mic_buffer[N:]
                self.callback(chunk)
            return

        if has_sys:
            while len(self.sys_buffer) >= N:
                chunk = self.sys_buffer[:N]
                self.sys_buffer = self.sys_buffer[N:]
                self.callback(chunk)

    def _trim_buffers(self):
        max_bytes = CHUNK_16K * 2 * MAX_BUFFER_CHUNKS
        if len(self.mic_buffer) > max_bytes:
            self.mic_buffer = self.mic_buffer[-max_bytes:]
        if len(self.sys_buffer) > max_bytes:
            self.sys_buffer = self.sys_buffer[-max_bytes:]

    def _mic_callback(self, in_data, frame_count, time_info, status):
        if self.is_running:
            self.mic_buffer += in_data
            self._trim_buffers()
            self._mix_and_send()
        return (None, pyaudio.paContinue)

    def _sys_callback(self, in_data, frame_count, time_info, status):
        if self.is_running:
            self.sys_buffer += self._sys_to_16k_mono(in_data)
            self._trim_buffers()
            self._mix_and_send()
        return (None, pyaudio.paContinue)

    def stop(self):
        self.is_running = False
        for s in [self.mic_stream, self.sys_stream]:
            if s:
                try:
                    s.stop_stream()
                    s.close()
                except Exception:
                    pass
        try:
            self.p.terminate()
        except Exception:
            pass
