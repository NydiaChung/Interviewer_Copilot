import pytest
from unittest.mock import MagicMock, patch

from server.search import SearchProcessor


@pytest.fixture
def mock_tavily_missing():
    with patch("server.search.TAVILY_API_KEY", None):
        yield


@pytest.fixture
def mock_tavily_present():
    with patch("server.search.TAVILY_API_KEY", "test_key"):
        yield


def test_search_processor_init_no_key(mock_tavily_missing):
    processor = SearchProcessor()
    assert processor.client is None


def test_search_processor_init_with_key(mock_tavily_present, mocker):
    mocker.patch("server.search.TavilyClient")
    processor = SearchProcessor()
    assert processor.client is not None


def test_search_no_client(mock_tavily_missing):
    processor = SearchProcessor()
    assert processor.search("test") == ""


def test_search_empty_query(mock_tavily_present, mocker):
    mocker.patch("server.search.TavilyClient")
    processor = SearchProcessor()
    assert processor.search("   ") == ""
    assert processor.search("") == ""


def test_search_success(mock_tavily_present, mocker):
    mock_client_cls = mocker.patch("server.search.TavilyClient")
    mock_instance = mock_client_cls.return_value
    mock_instance.search.return_value = {
        "results": [
            {"content": "result 1 fragment"},
            {"content": "result 2 fragment"},
            {"other": "missing content key"},
        ]
    }

    processor = SearchProcessor()
    res = processor.search("query")
    assert res == "result 1 fragment\nresult 2 fragment"
    mock_instance.search.assert_called_once_with(
        query="query", search_depth="advanced", max_results=3
    )


def test_search_exception(mock_tavily_present, mocker):
    mock_client_cls = mocker.patch("server.search.TavilyClient")
    mock_instance = mock_client_cls.return_value
    mock_instance.search.side_effect = Exception("network error")

    processor = SearchProcessor()
    res = processor.search("query")
    assert res == ""
