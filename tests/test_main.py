import pytest
from fastapi.testclient import TestClient
import json
import base64
import os
import io

from server.main import app
from server.utils.text import normalize_text as _normalize_text, text_similarity as _similarity, chunk_answer_text as _chunk_answer_text

client = TestClient(app)


def test_normalize_text():
    assert _normalize_text("  HeLLO   World  ") == "hello world"
    assert _normalize_text(None) == ""
    assert _normalize_text("") == ""


def test_similarity():
    assert _similarity("hello", "hello") == 1.0
    assert _similarity("abc", "") == 0.0
    assert _similarity(None, "abc") == 0.0


def test_chunk_answer_text():
    assert _chunk_answer_text("") == []
    assert _chunk_answer_text("hello") == ["hello"]
    # Test length >= 20
    assert _chunk_answer_text("12345678901234567890123") == [
        "12345678901234567890",
        "123",
    ]
    # Test split chars
    assert _chunk_answer_text("你好，世界。是一个测试！对于分块的作用；") == [
        "你好，世界。",
        "是一个测试！",
        "对于分块的作用；",
    ]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_set_context():
    response = client.post(
        "/set_context",
        json={
            "jd": "Software Engineer",
            "resume": "Backend dev",
            "extra_info": "Knows Python",
        },
    )
    assert response.status_code == 200
    from server.handlers.ws_handler import get_default_session

    session = get_default_session()
    assert session.jd_text == "Software Engineer"
    assert "【个人简历】" in session.resume_text
    assert "【其他补充信息】" in session.resume_text


def test_parse_resume_image():
    # .png
    response = client.post(
        "/parse_resume",
        files={"file": ("test.png", b"fake image content", "image/png")},
    )
    assert response.status_code == 200
    assert "暂未实现" in response.json()["text"]


def test_parse_resume_unsupported():
    response = client.post(
        "/parse_resume", files={"file": ("test.txt", b"txt", "text/plain")}
    )
    assert response.status_code == 400


def test_parse_resume_pdf(mocker):
    mock_fitz = mocker.MagicMock()
    mock_doc = mocker.MagicMock()
    mock_page = mocker.MagicMock()
    mock_page.get_text.return_value = "pdf content"
    mock_doc.__iter__.return_value = [mock_page]
    mock_fitz.open.return_value = mock_doc

    import sys

    mocker.patch.dict(sys.modules, {"fitz": mock_fitz})

    response = client.post(
        "/parse_resume", files={"file": ("test.pdf", b"pdf data", "application/pdf")}
    )
    assert response.status_code == 200
    assert response.json()["text"] == "pdf content"


def test_parse_resume_pdf_missing_dependency(mocker):
    import sys

    mocker.patch.dict(sys.modules, {"fitz": None})
    response = client.post(
        "/parse_resume", files={"file": ("test.pdf", b"pdf data", "application/pdf")}
    )
    assert response.status_code == 500


def test_parse_resume_docx(mocker):
    mock_docx = mocker.MagicMock()
    mock_doc = mocker.MagicMock()
    mock_para = mocker.MagicMock()
    mock_para.text = "docx content"
    mock_doc.paragraphs = [mock_para]
    mock_docx.Document.return_value = mock_doc

    import sys

    mocker.patch.dict(sys.modules, {"docx": mock_docx})

    response = client.post(
        "/parse_resume",
        files={
            "file": (
                "test.docx",
                b"docx data",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 200
    assert response.json()["text"] == "docx content"


def test_parse_resume_docx_missing_dependency(mocker):
    import sys

    mocker.patch.dict(sys.modules, {"docx": None})
    response = client.post(
        "/parse_resume",
        files={
            "file": (
                "test.docx",
                b"docx data",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert response.status_code == 500


def test_parse_resume_exception(mocker):
    import sys

    mock_fitz = mocker.MagicMock()
    mock_fitz.open.side_effect = Exception("general error")
    mocker.patch.dict(sys.modules, {"fitz": mock_fitz})

    response = client.post(
        "/parse_resume",
        files={"file": ("test.pdf", b"fake content", "application/pdf")},
    )
    assert response.status_code == 500
    assert "general error" in response.text
