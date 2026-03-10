import math
import struct

from server.voiceprint import VoiceprintTracker


def _tone(freq_hz: float, amp: int, samples: int = 1600, sr: int = 16000) -> bytes:
    buf = bytearray()
    for i in range(samples):
        v = int(amp * math.sin(2 * math.pi * freq_hz * (i / sr)))
        v = max(-32768, min(32767, v))
        buf.extend(struct.pack("<h", v))
    return bytes(buf)


def test_voiceprint_same_speaker_is_stable():
    tracker = VoiceprintTracker(assign_threshold=0.20, min_rms=50, lookback_seconds=1.0)
    chunk = _tone(220, 5000)
    ids = [tracker.update_audio(chunk, ts=0.08 * i) for i in range(1, 8)]
    ids = [sid for sid in ids if sid is not None]

    assert ids
    assert len(set(ids)) == 1
    assert tracker.dominant_speaker(ts=0.70) == ids[-1]


def test_voiceprint_detects_speaker_switch():
    tracker = VoiceprintTracker(assign_threshold=0.14, min_rms=50, lookback_seconds=1.2)
    speaker_a = _tone(180, 4200)
    speaker_b = _tone(980, 12000)

    sid_a = None
    for i in range(6):
        sid_a = tracker.update_audio(speaker_a, ts=0.05 * (i + 1))
    sid_b = None
    for i in range(6):
        sid_b = tracker.update_audio(speaker_b, ts=0.50 + 0.05 * (i + 1))

    assert sid_a is not None
    assert sid_b is not None
    assert sid_a != sid_b
    assert tracker.dominant_speaker(ts=1.00) == sid_b


def test_voiceprint_ignores_silence_and_bad_frames():
    tracker = VoiceprintTracker(min_rms=120)
    assert tracker.update_audio(b"\x00" * 640, ts=0.1) is None
    assert tracker.update_audio(b"\x00" * 641, ts=0.2) is None
    assert tracker.dominant_speaker(ts=0.3) is None


def test_voiceprint_max_speakers_fallback(mocker):
    tracker = VoiceprintTracker(assign_threshold=0.1, max_speakers=2)

    mocker.patch.object(
        VoiceprintTracker,
        "_extract_features",
        side_effect=[
            (0.1, 0.1, 0.1, 0.1),
            (0.9, 0.9, 0.9, 0.9),
            (0.15, 0.15, 0.15, 0.15),
        ],
    )

    sid1 = tracker.update_audio(b"A" * 640, ts=0.1)
    sid2 = tracker.update_audio(b"B" * 640, ts=0.2)
    sid3 = tracker.update_audio(b"C" * 640, ts=0.3)

    assert sid1 is not None and sid2 is not None and sid3 is not None
    assert sid1 != sid2
    assert sid3 == sid1


def test_voiceprint_short_chunk_returns_none():
    tracker = VoiceprintTracker()
    assert tracker.update_audio(b"short", ts=0.1) is None


def test_voiceprint_low_rms_returns_none():
    tracker = VoiceprintTracker(min_rms=20000)
    chunk = _tone(200, 15)
    sid = tracker.update_audio(chunk, ts=0.1)
    assert sid is None


def test_voiceprint_cleanup_old_events():
    tracker = VoiceprintTracker(lookback_seconds=1.0)
    chunk = _tone(200, 5000)
    tracker.update_audio(chunk, ts=0.1)
    tracker.update_audio(chunk, ts=3.1)

    assert len(tracker._events) == 1
    assert tracker._events[0][0] == 3.1


def test_voiceprint_dominant_speaker_age_filters():
    tracker = VoiceprintTracker(lookback_seconds=1.0)
    chunk = _tone(200, 5000)
    sid = tracker.update_audio(chunk, ts=1.0)

    assert tracker.dominant_speaker(ts=0.5) is None
    assert tracker.dominant_speaker(ts=2.5) is None


def test_voiceprint_audioop_error_mock(mocker):
    tracker = VoiceprintTracker()
    mocker.patch.object(
        VoiceprintTracker, "_extract_features", return_value=(0.5, 0.5, 0.5, 0.5)
    )
    sid = tracker.update_audio(b"123", ts=0.1)
    assert sid is None
