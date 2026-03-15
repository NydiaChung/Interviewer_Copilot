"""搜索模块 — 基于 Tavily 的网络搜索。"""

import os
from tavily import TavilyClient

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class SearchProcessor:
    """Tavily 网络搜索处理器。"""

    def __init__(self):
        if not TAVILY_API_KEY:
            # 未配置 Key 时不崩溃，仅禁用搜索功能
            self.client = None
        else:
            self.client = TavilyClient(api_key=TAVILY_API_KEY)

    def search(self, query: str, max_results: int = 3) -> str:
        """执行网络搜索，返回拼接后的上下文文本。"""
        if not self.client or not query.strip():
            return ""

        try:
            response = self.client.search(
                query=query, search_depth="advanced", max_results=max_results
            )

            # 将搜索结果格式化为上下文字符串
            context_pieces = []
            for result in response.get("results", []):
                snippet = result.get("content", "")
                if snippet:
                    context_pieces.append(snippet)

            return "\n".join(context_pieces)
        except Exception as e:
            print(f"[Search] Error performing web search: {e}")
            return ""


# 单例
search_processor = SearchProcessor()
