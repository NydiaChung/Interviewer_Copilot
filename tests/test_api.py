import os
import pytest
import io
import json
import base64
import asyncio
import inspect
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# 设置环境变量，防止启动时因为缺少 Key 而崩溃
os.environ["OPENAI_API_KEY"] = "dummy"
os.environ["DASHSCOPE_API_KEY"] = "dummy"
os.environ["GEMINI_API_KEY"] = "dummy"
os.environ["DOUBAO_APP_ID"] = "dummy"
os.environ["DOUBAO_ACCESS_TOKEN"] = "dummy"

from server.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_set_context():
    payload = {
        "jd": "Software Engineer JD",
        "resume": "Experienced Developer Resume",
        "extra_info": "Supplemental data",
    }
    response = client.post("/set_context", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    from server.handlers.ws_handler import get_default_session

    session = get_default_session()
    assert session.jd_text == "Software Engineer JD"
    assert "Experienced Developer Resume" in session.resume_text
    assert "Supplemental data" in session.resume_text


def test_parse_resume_pdf_mock():
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Extracted PDF Text"
    mock_doc.__iter__.return_value = [mock_page]

    with patch("fitz.open", return_value=mock_doc):
        file_content = b"%PDF-1.4 dummy content"
        files = {"file": ("resume.pdf", file_content, "application/pdf")}
        response = client.post("/parse_resume", files=files)

        assert response.status_code == 200
        assert response.json()["text"] == "Extracted PDF Text"


def test_parse_resume_docx_mock():
    mock_doc = MagicMock()
    mock_para = MagicMock()
    mock_para.text = "Extracted Docx Paragraph"
    mock_doc.paragraphs = [mock_para]

    with patch("docx.Document", return_value=mock_doc):
        file_content = b"docx content"
        files = {
            "file": (
                "resume.docx",
                file_content,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        }
        response = client.post("/parse_resume", files=files)

        assert response.status_code == 200
        assert response.json()["text"] == "Extracted Docx Paragraph"


def test_parse_resume_unsupported():
    files = {"file": ("resume.txt", b"txt content", "text/plain")}
    response = client.post("/parse_resume", files=files)
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


class _FakeASR:
    def __init__(self):
        self.callback = None
        self.loop = None

    def set_callback(self, callback, loop):
        self.callback = callback
        self.loop = loop

    def start(self):
        return

    def add_audio(self, chunk: bytes):
        return

    def stop(self):
        return


class _RecordingASR(_FakeASR):
    def __init__(self):
        super().__init__()
        self.audio_chunks = []

    def add_audio(self, chunk: bytes):
        self.audio_chunks.append(chunk)


class _TriggeringASR(_RecordingASR):
    def __init__(self, trigger_text: str = ""):
        super().__init__()
        self.trigger_text = trigger_text
        self.callback_is_async = False

    def set_callback(self, callback, loop):
        super().set_callback(callback, loop)
        self.callback_is_async = inspect.iscoroutinefunction(callback)

    def add_audio(self, chunk: bytes):
        super().add_audio(chunk)
        if self.trigger_text and self.callback and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.callback(self.trigger_text, False), self.loop
            )


class _FailStartASR(_FakeASR):
    def start(self):
        raise RuntimeError("asr start failed")


class _FakeLLM:
    def __init__(self):
        self.answer_calls = 0
        self.analysis_calls = 0

    async def generate_outline(self, jd: str, resume: str, question: str) -> str:
        return "outline"

    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        self.answer_calls += 1
        return f"answer:{question}"

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        self.analysis_calls += 1
        return "analysis-ok"


class _FailingLLM(_FakeLLM):
    async def generate_answer(self, jd: str, resume: str, question: str) -> str:
        raise RuntimeError("answer failed")

    async def generate_analysis(self, jd: str, resume: str, history: str) -> str:
        raise RuntimeError("analysis failed")


def _patch_llm_and_asr(fake_llm, fake_asr_or_factory):
    """Helper to patch llm_processor and get_asr_processor in their actual modules."""
    import server.handlers.command_handler as cmd_mod
    import server.handlers.answer_scheduler as ans_mod
    import server.handlers.ws_handler as ws_mod

    if callable(fake_asr_or_factory) and not isinstance(fake_asr_or_factory, _FakeASR):
        asr_patch = patch.object(ws_mod, "get_asr_processor", side_effect=fake_asr_or_factory)
    else:
        asr_patch = patch.object(ws_mod, "get_asr_processor", return_value=fake_asr_or_factory)

    return (
        patch.object(cmd_mod, "llm_processor", fake_llm),
        patch.object(ans_mod, "llm_processor", fake_llm),
        asr_patch,
    )


def test_manual_question_does_not_trigger_analysis():
    fake_llm = _FakeLLM()
    p1, p2, p3 = _patch_llm_and_asr(fake_llm, _FakeASR())
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "manual_question", "text": "你好"}))
            incremental = ws.receive_json()
            assert incremental["type"] == "incremental"
            response = ws.receive_json()
            assert response["type"] == "answer"
            assert response["answer"] == "answer:你好"

    assert fake_llm.answer_calls == 1
    assert fake_llm.analysis_calls == 0


def test_end_session_triggers_analysis():
    fake_llm = _FakeLLM()
    p1, p2, p3 = _patch_llm_and_asr(fake_llm, _FakeASR())
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "end_session"}))
            response = ws.receive_json()
            assert response["type"] == "analysis"
            assert response["answer"] == "analysis-ok"

    assert fake_llm.analysis_calls == 1


def test_websocket_uses_per_connection_asr_instance():
    fake_llm = _FakeLLM()
    factory_calls = []

    def _factory():
        factory_calls.append(1)
        return _FakeASR()

    p1, p2, p3 = _patch_llm_and_asr(fake_llm, _factory)
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws1:
            ws1.send_text(json.dumps({"command": "end_session"}))
            ws1.receive_json()
        with client.websocket_connect("/ws/audio") as ws2:
            ws2.send_text(json.dumps({"command": "end_session"}))
            ws2.receive_json()

    assert len(factory_calls) == 2


def test_manual_question_returns_fallback_when_llm_fails():
    failing_llm = _FailingLLM()
    p1, p2, p3 = _patch_llm_and_asr(failing_llm, _FakeASR())
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "manual_question", "text": "你好"}))
            incremental = ws.receive_json()
            assert incremental["type"] == "incremental"
            response = ws.receive_json()
            assert response["type"] == "answer"
            assert "抱歉，我刚才没来得及生成完整回答" in response["answer"]


def test_end_session_returns_fallback_when_analysis_fails():
    failing_llm = _FailingLLM()
    p1, p2, p3 = _patch_llm_and_asr(failing_llm, _FakeASR())
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "end_session"}))
            response = ws.receive_json()
            assert response["type"] == "analysis"
            assert "复盘生成超时或失败" in response["answer"]


def test_dual_stream_text_audio_frame_is_forwarded_to_asr():
    """双流模式下桌面端会发送 text(JSON+base64) 音频帧，后端也应转发给 ASR。"""
    fake_asr = _RecordingASR()
    fake_llm = _FakeLLM()
    raw = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    audio_payload = {
        "type": "audio",
        "channel": "system",
        "data": base64.b64encode(raw).decode("ascii"),
    }

    p1, p2, p3 = _patch_llm_and_asr(fake_llm, fake_asr)
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps(audio_payload))
            ws.send_text(json.dumps({"command": "end_session"}))
            response = ws.receive_json()
            assert response["type"] == "analysis"

    assert fake_asr.audio_chunks, "text audio payload was not forwarded to ASR"
    assert fake_asr.audio_chunks[0] == raw


def test_candidate_channel_callback_is_async_and_emits_incremental():
    main_asr = _RecordingASR()
    candidate_asr = _TriggeringASR(trigger_text="候选人：您好，我先做个自我介绍。")
    fake_llm = _FakeLLM()
    raw = b"\x10\x20\x30\x40\x50\x60\x70\x80"
    audio_payload = {
        "type": "audio",
        "channel": "mic",
        "data": base64.b64encode(raw).decode("ascii"),
    }
    providers = [main_asr, candidate_asr]

    def _factory():
        return providers.pop(0)

    p1, p2, p3 = _patch_llm_and_asr(fake_llm, _factory)
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps(audio_payload))
            incremental = ws.receive_json()
            assert incremental["type"] == "incremental"
            assert incremental["speaker_role"] == "candidate"
            assert "自我介绍" in incremental["text"]

            ws.send_text(json.dumps({"command": "end_session"}))
            analysis = ws.receive_json()
            assert analysis["type"] == "analysis"

    assert candidate_asr.audio_chunks, "candidate audio was not forwarded"
    assert candidate_asr.audio_chunks[0] == raw
    assert (
        candidate_asr.callback_is_async
    ), "candidate ASR callback must be async coroutine"


def test_websocket_keeps_alive_when_asr_start_fails():
    fake_llm = _FakeLLM()
    p1, p2, p3 = _patch_llm_and_asr(fake_llm, _FailStartASR())
    with p1, p2, p3:
        with client.websocket_connect("/ws/audio") as ws:
            warning = ws.receive_json()
            assert warning["type"] == "incremental"
            assert "语音识别暂不可用" in warning["text"]

            ws.send_text(json.dumps({"command": "manual_question", "text": "你好"}))
            incremental = ws.receive_json()
            assert incremental["type"] == "incremental"
            answer = ws.receive_json()
            assert answer["type"] == "answer"
            assert answer["answer"] == "answer:你好"
