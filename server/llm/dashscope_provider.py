"""DashScope (通义千问) LLM 提供商。"""

import asyncio
import os

from server.llm.base import BaseLLMProcessor


class DashScopeProcessor(BaseLLMProcessor):
    outline_model = "qwen_plus"
    answer_model = "qwen_plus"
    analysis_model = "qwen_max"

    def __init__(self):
        import dashscope

        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("DASHSCOPE_API_KEY environment variable not set")
        dashscope.api_key = api_key

    async def _call(self, prompt: str, model: str) -> str:
        import dashscope

        model_map = {
            "qwen_plus": dashscope.Generation.Models.qwen_plus,
            "qwen_max": dashscope.Generation.Models.qwen_max,
        }
        resolved_model = model_map.get(model, model)

        response = await asyncio.to_thread(
            dashscope.Generation.call,
            model=resolved_model,
            messages=[{"role": "user", "content": prompt}],
            result_format="message",
            temperature=0.7,
        )

        if response.status_code == 200:
            return response.output.choices[0].message.content
        print(
            f"[LLM] DashScope error: {response.code} - {response.message}"
        )
        return ""
