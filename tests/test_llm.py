import os
import pytest
from unittest.mock import patch, MagicMock
from server.llm import (
    get_llm_processor,
    OpenAIProcessor,
    DashScopeProcessor,
    GeminiProcessor,
    FallbackLLMProcessor,
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


def test_get_llm_processor_auto_mode_prefers_available_chain():
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "auto",
            "LLM_AUTO_ORDER": "dashscope,openai,gemini",
            "DASHSCOPE_API_KEY": "dash-key",
            "OPENAI_API_KEY": "openai-key",
        },
        clear=True,
    ):
        with patch("dashscope.Generation"), patch("openai.OpenAI"):
            processor = get_llm_processor()
            assert isinstance(processor, FallbackLLMProcessor)


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
async def test_openai_processor_none_content_returns_empty_string():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
        mock_openai = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_openai.chat.completions.create.return_value = mock_response

        with patch("openai.OpenAI", return_value=mock_openai):
            processor = OpenAIProcessor()
            result = await processor.generate_answer("jd", "resume", "question")
            assert result == ""


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


# ----------------- Missing Coverage Tests -----------------


def test_module_not_found_prompt_import(mocker):
    import sys
    from unittest.mock import MagicMock

    dummy_prompt = MagicMock()
    dummy_prompt.INTERVIEW_PROMPT = "inter"
    dummy_prompt.OUTLINE_PROMPT = "out"
    dummy_prompt.ANALYSIS_PROMPT = "ana"

    # Force import error for server.prompt
    mocker.patch.dict(sys.modules, {"server.prompt": None, "prompt": dummy_prompt})
    from server import llm
    import importlib

    importlib.reload(llm)


@pytest.mark.asyncio
async def test_base_llm_processor_not_implemented():
    from server.llm import BaseLLMProcessor

    base = BaseLLMProcessor()
    with pytest.raises(NotImplementedError):
        await base.generate_outline("", "", "")
    with pytest.raises(NotImplementedError):
        await base.generate_answer("", "", "")
    with pytest.raises(NotImplementedError):
        await base.generate_analysis("", "", "")


def test_safe_text_non_str():
    from server.llm import _safe_text

    assert _safe_text(123) == "123"


def test_processor_init_missing_keys():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIProcessor()
        with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
            DashScopeProcessor()
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            GeminiProcessor()


@pytest.mark.asyncio
async def test_openai_generate_outline():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
        with patch("openai.OpenAI") as mock_openai:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "outline result"
            mock_openai.return_value.chat.completions.create.return_value = mock_resp

            p = OpenAIProcessor()
            assert await p.generate_outline("jd", "resume", "q") == "outline result"
            assert await p.generate_outline("", "", "   ") == ""


@pytest.mark.asyncio
async def test_openai_generate_analysis():
    with patch.dict(os.environ, {"OPENAI_API_KEY": "test"}):
        with patch("openai.OpenAI") as mock_openai:
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock()]
            mock_resp.choices[0].message.content = "analysis result"
            mock_openai.return_value.chat.completions.create.return_value = mock_resp

            p = OpenAIProcessor()
            assert await p.generate_analysis("jd", "resume", "h") == "analysis result"
            assert (
                await p.generate_analysis("", "", "   ")
                == "本次面试没有记录下足够的对话，无法进行深入复盘。"
            )


@pytest.mark.asyncio
async def test_dashscope_generate_outline_and_error():
    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test"}):
        with patch("dashscope.Generation.call") as mock_call:
            p = DashScopeProcessor()

            # empty question
            assert await p.generate_outline("jd", "resume", "   ") == ""

            # success
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.output.choices = [MagicMock()]
            mock_resp.output.choices[0].message.content = "ds outline"
            mock_call.return_value = mock_resp
            assert await p.generate_outline("jd", "resume", "q") == "ds outline"

            # error
            mock_resp.status_code = 400
            assert await p.generate_outline("jd", "resume", "q") == ""


@pytest.mark.asyncio
async def test_dashscope_generate_answer_empty_and_error():
    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test"}):
        with patch("dashscope.Generation.call") as mock_call:
            p = DashScopeProcessor()
            assert await p.generate_answer("jd", "resume", "   ") == ""

            mock_resp = MagicMock()
            mock_resp.status_code = 400
            mock_call.return_value = mock_resp
            assert await p.generate_answer("jd", "resume", "q") == ""


@pytest.mark.asyncio
async def test_dashscope_generate_analysis():
    with patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test"}):
        with patch("dashscope.Generation.call") as mock_call:
            p = DashScopeProcessor()
            assert (
                await p.generate_analysis("", "", "   ")
                == "本次面试没有记录下足够的对话，无法进行深入复盘。"
            )

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.output.choices = [MagicMock()]
            mock_resp.output.choices[0].message.content = "ds analysis"
            mock_call.return_value = mock_resp
            assert await p.generate_analysis("j", "r", "h") == "ds analysis"

            mock_resp.status_code = 400
            assert await p.generate_analysis("j", "r", "h") == "分析生成失败。"


@pytest.mark.asyncio
async def test_gemini_generate_methods():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}):
        with patch("google.genai.Client") as mock_client_cls:
            mock_client = mock_client_cls.return_value
            mock_resp = MagicMock()
            mock_resp.text = "gemini text"
            mock_client.models.generate_content.return_value = mock_resp

            p = GeminiProcessor()
            assert await p.generate_outline("j", "r", "   ") == ""
            assert await p.generate_outline("j", "r", "q") == "gemini text"
            assert await p.generate_answer("j", "r", "   ") == ""
            assert (
                await p.generate_analysis("j", "r", "   ")
                == "本次面试没有记录下足够的对话，无法进行深入复盘。"
            )
            assert await p.generate_analysis("j", "r", "h") == "gemini text"


@pytest.mark.asyncio
async def test_fallback_processor_methods(mocker):
    from server.llm import BaseLLMProcessor

    class DummyProcessor(BaseLLMProcessor):
        async def generate_outline(self, *args):
            return "outline"

        async def generate_answer(self, *args):
            return "answer"

        async def generate_analysis(self, *args):
            return "analysis"

    class FailingProcessor(BaseLLMProcessor):
        async def generate_outline(self, *args):
            raise ValueError("err")

        async def generate_answer(self, *args):
            raise ValueError("err")

        async def generate_analysis(self, *args):
            raise ValueError("err")

    class EmptyProcessor(BaseLLMProcessor):
        async def generate_outline(self, *args):
            return ""

    p = FallbackLLMProcessor(
        [
            ("fail", FailingProcessor()),
            ("empty", EmptyProcessor()),
            ("dummy", DummyProcessor()),
        ]
    )
    assert await p.generate_outline("j", "r", "q") == "outline"
    assert await p.generate_answer("j", "r", "q") == "answer"
    assert await p.generate_analysis("j", "r", "h") == "analysis"

    p_fail = FallbackLLMProcessor([("fail", FailingProcessor())])
    with pytest.raises(ValueError):
        await p_fail.generate_outline("j", "r", "q")


def test_build_processor_and_get_llm_processor(mocker):
    from server.llm import _build_processor, get_llm_processor, _parse_order

    # parse order empty/duplicates
    assert _parse_order(" , openai, OpenAI ,") == ["openai"]

    # build processor missing key
    with patch.dict(os.environ, {}, clear=True):
        assert _build_processor("openai") is None
        assert _build_processor("dashscope") is None
        assert _build_processor("gemini") is None
        assert _build_processor("unknown") is None

        # test auto mode with empty built_providers
        with pytest.raises(ValueError, match="No available LLM provider"):
            get_llm_processor()

    # build processor exceptions
    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "x", "DASHSCOPE_API_KEY": "x", "GEMINI_API_KEY": "x"},
        clear=True,
    ):
        mocker.patch("server.llm.OpenAIProcessor", side_effect=Exception("e"))
        mocker.patch("server.llm.DashScopeProcessor", side_effect=Exception("e"))
        mocker.patch("server.llm.GeminiProcessor", side_effect=Exception("e"))
        assert _build_processor("openai") is None
        assert _build_processor("dashscope") is None
        assert _build_processor("gemini") is None

    # single provider auto mode
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "auto", "LLM_AUTO_ORDER": "openai", "OPENAI_API_KEY": "x"},
        clear=True,
    ):
        mocker.patch("server.llm.OpenAIProcessor")
        res = get_llm_processor()
        assert res is not None  # returns processor directly

    # invalid explicit provider
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):  # missing key
        with pytest.raises(
            ValueError, match="openai provider is not configured correctly"
        ):
            get_llm_processor()
