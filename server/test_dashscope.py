import sys
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
import os
import time

dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")


class Callback(RecognitionCallback):
    def on_event(self, result: RecognitionResult) -> None:
        print("Event:", result.get_sentence())


callback = Callback()
recognition = Recognition(
    model="paraformer-realtime-v2", format="pcm", sample_rate=16000, callback=callback
)

recognition.start()
print("Started")
import wave

# make a dummy audio file
import numpy as np
import io

fs = 16000
duration = 1.0  # seconds
t = np.linspace(0, duration, int(fs * duration), endpoint=False)
audio_data = (np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16).tobytes()

for i in range(0, len(audio_data), 3200):
    chunk = audio_data[i : i + 3200]
    recognition.send_audio_frame(chunk)
    time.sleep(0.1)

recognition.stop()
