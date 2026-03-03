import os
import pytest
import io
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# 设置环境变量，防止 main.py 在启动时因为缺少 Key 而崩溃
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

    # 验证全局变量是否已更新 (由于 main.py 在同一个进程通过 global 变量管理，这里可以直接测试)
    from server import main

    assert main.JD_TEXT == "Software Engineer JD"
    assert "Experienced Developer Resume" in main.RESUME_TEXT
    assert "Supplemental data" in main.RESUME_TEXT


def test_parse_resume_pdf_mock():
    # 模拟 fitz (PyMuPDF)
    mock_doc = MagicMock()
    mock_page = MagicMock()
    mock_page.get_text.return_value = "Extracted PDF Text"
    mock_doc.__iter__.return_value = [mock_page]

    with patch("fitz.open", return_value=mock_doc):
        # 创建一个假的 PDF 文件内容
        file_content = b"%PDF-1.4 dummy content"
        files = {"file": ("resume.pdf", file_content, "application/pdf")}
        response = client.post("/parse_resume", files=files)

        assert response.status_code == 200
        assert response.json()["text"] == "Extracted PDF Text"


def test_parse_resume_docx_mock():
    # 模拟 docx.Document
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


def test_manual_question_does_not_trigger_analysis():
    from server import main

    fake_llm = _FakeLLM()
    with patch.object(main, "llm_processor", fake_llm), patch.object(
        main, "get_asr_processor", return_value=_FakeASR()
    ):
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "manual_question", "text": "你好"}))
            response = ws.receive_json()
            assert response["type"] == "answer"
            assert response["answer"] == "answer:你好"

    assert fake_llm.answer_calls == 1
    assert fake_llm.analysis_calls == 0


def test_end_session_triggers_analysis():
    from server import main

    fake_llm = _FakeLLM()
    with patch.object(main, "llm_processor", fake_llm), patch.object(
        main, "get_asr_processor", return_value=_FakeASR()
    ):
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "end_session"}))
            response = ws.receive_json()
            assert response["type"] == "analysis"
            assert response["answer"] == "analysis-ok"

    assert fake_llm.analysis_calls == 1


def test_websocket_uses_per_connection_asr_instance():
    from server import main

    fake_llm = _FakeLLM()
    factory_calls = []

    def _factory():
        factory_calls.append(1)
        return _FakeASR()

    with patch.object(main, "llm_processor", fake_llm), patch.object(
        main, "get_asr_processor", side_effect=_factory
    ):
        with client.websocket_connect("/ws/audio") as ws1:
            ws1.send_text(json.dumps({"command": "end_session"}))
            ws1.receive_json()
        with client.websocket_connect("/ws/audio") as ws2:
            ws2.send_text(json.dumps({"command": "end_session"}))
            ws2.receive_json()

    assert len(factory_calls) == 2


def test_manual_question_returns_fallback_when_llm_fails():
    from server import main

    failing_llm = _FailingLLM()
    with patch.object(main, "llm_processor", failing_llm), patch.object(
        main, "get_asr_processor", return_value=_FakeASR()
    ):
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "manual_question", "text": "你好"}))
            response = ws.receive_json()
            assert response["type"] == "answer"
            assert "抱歉，我刚才没来得及生成完整回答" in response["answer"]


def test_end_session_returns_fallback_when_analysis_fails():
    from server import main

    failing_llm = _FailingLLM()
    with patch.object(main, "llm_processor", failing_llm), patch.object(
        main, "get_asr_processor", return_value=_FakeASR()
    ):
        with client.websocket_connect("/ws/audio") as ws:
            ws.send_text(json.dumps({"command": "end_session"}))
            response = ws.receive_json()
            assert response["type"] == "analysis"
            assert "复盘生成超时或失败" in response["answer"]
