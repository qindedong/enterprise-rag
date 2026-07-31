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
        # 视觉模型：未单独配置时回退主模型（不支持视觉时调用方降级）
        self.vision_model = getattr(settings, "VISION_MODEL", None) or self.model
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

        self._client = AsyncOpenAI(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            timeout=120.0,
            max_retries=3,
        )
        # 视觉模型可走独立厂商端点（如主模型用 DeepSeek、视觉用智谱 GLM-4V）
        vision_base = getattr(settings, "VISION_BASE_URL", "") or settings.LLM_BASE_URL
        vision_key = getattr(settings, "VISION_API_KEY", "") or settings.LLM_API_KEY
        self._vision_client = AsyncOpenAI(
            api_key=vision_key,
            base_url=vision_base,
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

    async def generate_with_image(
        self, prompt: str, image_bytes: bytes, mime: str = "image/png"
    ) -> dict:
        """
        多模态图像理解（OpenAI Compatible vision 格式）

        Args:
            prompt: 针对图片的提问/指令
            image_bytes: 图片二进制内容
            mime: 图片 MIME 类型

        Returns:
            包含 answer, usage, finish_reason 的字典

        Raises:
            LLMException: 模型不支持视觉或调用失败（调用方应降级处理）
        """
        import base64

        b64 = base64.b64encode(image_bytes).decode("ascii")
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }]
        try:
            response = await self._vision_client.chat.completions.create(
                model=self.vision_model,
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
            raise LLMException(f"视觉模型调用失败: {e}") from e
