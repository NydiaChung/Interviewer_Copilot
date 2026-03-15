"""ASR 提供商抽象基类。"""

import abc


class ASRProvider(abc.ABC):
    """所有 ASR 提供商必须实现的接口。"""

    def __init__(self):
        self.on_text_update = None
        self.loop = None
        self.is_started = False

    def set_callback(self, on_text_update_func, loop):
        """注册文本回调和事件循环。"""
        self.on_text_update = on_text_update_func
        self.loop = loop

    @abc.abstractmethod
    def start(self):
        """启动 ASR 连接。"""

    @abc.abstractmethod
    def add_audio(self, audio_chunk: bytes):
        """推送音频数据。"""

    @abc.abstractmethod
    def stop(self):
        """停止 ASR 连接。"""
