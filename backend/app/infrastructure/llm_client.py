"""
LLM 服务客户端

封装 OpenAI Compatible API 的 LLM 调用。
支持流式生成（SSE）和非流式生成，自动重试。
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.exceptions import LLMException
from app.core.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """LLM 服务客户端 — OpenAI Compatible API"""

    def __init__(self):
        settings = get_settings()
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=120.0,
            max_retries=3,
        )

    async def generate(self, messages: list[dict]) -> dict:
        """
        非流式生成

        Args:
            messages: OpenAI 格式的消息列表 [{"role": "...", "content": "..."}]

        Returns:
            包含 answer, usage, finish_reason 的字典
        """
        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )
            choice = response.choices[0]
            return {
                "answer": choice.message.content or "",
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                "finish_reason": choice.finish_reason,
            }
        except Exception as e:
            raise LLMException(f"LLM 调用失败: {e}") from e

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        """
        流式生成 — 逐 Token 返回

        Args:
            messages: OpenAI 格式的消息列表

        Yields:
            每个生成的文本片段
        """
        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            raise LLMException(f"LLM 流式调用失败: {e}") from e
