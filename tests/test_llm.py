import os
import pytest
from unittest.mock import patch, MagicMock
from server.llm import (
    get_llm_processor,
    OpenAIProcessor,
    DashScopeProcessor,
    GeminiProcessor,
)


def test_get_llm_processor_factory():
    # 测试默认 provider (openai)
    with patch.dict(
        os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}
    ):
        with patch("openai.OpenAI"):
            processor = get_llm_processor()
            assert isinstance(processor, OpenAIProcessor)

    # 测试 dashscope provider
    with patch.dict(
        os.environ, {"LLM_PROVIDER": "dashscope", "DASHSCOPE_API_KEY": "test-key"}
    ):
        with patch("dashscope.Generation"):
            processor = get_llm_processor()
            assert isinstance(processor, DashScopeProcessor)

    # 测试 gemini provider
    with patch.dict(
        os.environ, {"LLM_PROVIDER": "gemini", "GEMINI_API_KEY": "test-key"}
    ):
        with patch("google.genai.Client"):
            processor = get_llm_processor()
            assert isinstance(processor, GeminiProcessor)


@pytest.mark.asyncio
async def test_openai_processor_empty_question():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        with patch("openai.OpenAI"):
            processor = OpenAIProcessor()
            result = await processor.generate_answer("", "", "")
            assert result == ""
            result = await processor.generate_outline("", "", "   ")
            assert result == ""


@pytest.mark.asyncio
async def test_openai_processor_generate_answer():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "  Mocked AI Answer  "
        mock_openai.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_openai):
            processor = OpenAIProcessor()
            result = await processor.generate_answer("jd", "resume", "question")
            assert result == "Mocked AI Answer"
            # 验证 prompt 是否正确包含输入
            mock_openai.chat.completions.create.assert_called_once()
            args, kwargs = mock_openai.chat.completions.create.call_args
            assert "jd" in kwargs["messages"][0]["content"]


@pytest.mark.asyncio
async def test_dashscope_processor_generate_answer():
    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test-key"}):
        mock_gen = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.choices = [MagicMock()]
        mock_response.output.choices[0].message.content = "Qwen Answer"
        mock_gen.call.return_value = mock_response

        with patch("dashscope.Generation", mock_gen):
            processor = DashScopeProcessor()
            result = await processor.generate_answer("jd", "resume", "question")
            assert result == "Qwen Answer"


@pytest.mark.asyncio
async def test_gemini_processor_generate_answer():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Gemini Answer"
        mock_client.models.generate_content.return_value = mock_response

        with patch("google.genai.Client", return_value=mock_client):
            processor = GeminiProcessor()
            result = await processor.generate_answer("jd", "resume", "question")
            assert result == "Gemini Answer"
