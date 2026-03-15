"""OpenAI LLM 提供商。"""

import asyncio
import os

from server.llm.base import BaseLLMProcessor


class OpenAIProcessor(BaseLLMProcessor):
    outline_model = "gpt-4o-mini"
    answer_model = "gpt-4o-mini"
    analysis_model = "gpt-4o"

    def __init__(self):
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = OpenAI(api_key=api_key)

    async def _call(self, prompt: str, model: str) -> str:
        response = await asyncio.to_thread(
            self.client.chat.completions.create,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1500 if model == "gpt-4o" else 200,
        )
        return response.choices[0].message.content
