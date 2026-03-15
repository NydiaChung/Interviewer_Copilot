"""Google Gemini LLM 提供商。"""

import asyncio
import os

from server.llm.base import BaseLLMProcessor


class GeminiProcessor(BaseLLMProcessor):
    outline_model = "gemini-2.5-flash"
    answer_model = "gemini-2.5-flash"
    analysis_model = "gemini-2.5-pro"

    def __init__(self):
        from google import genai

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        self.client = genai.Client(api_key=api_key)

    async def _call(self, prompt: str, model: str) -> str:
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=model,
            contents=prompt,
        )
        return response.text
