"""Search module using Tavily."""

import os
from tavily import TavilyClient

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


class SearchProcessor:
    """Tavily search processor for web context."""

    def __init__(self):
        if not TAVILY_API_KEY:
            # We don't want to crash if it's not set, just disable search.
            self.client = None
        else:
            self.client = TavilyClient(api_key=TAVILY_API_KEY)

    def search(self, query: str, max_results: int = 3) -> str:
        """Perform a web search and return a built context string."""
        if not self.client or not query.strip():
            return ""

        try:
            response = self.client.search(
                query=query, search_depth="advanced", max_results=max_results
            )

            # Format the results into a context string
            context_pieces = []
            for result in response.get("results", []):
                snippet = result.get("content", "")
                if snippet:
                    context_pieces.append(snippet)

            return "\n".join(context_pieces)
        except Exception as e:
            print(f"[Search] Error performing web search: {e}")
            return ""


# Singleton instance
search_processor = SearchProcessor()
