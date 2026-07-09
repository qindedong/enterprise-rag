"""
Embedding 服务客户端

封装 OpenAI Compatible API 的文本向量化请求。
支持多模型切换、批量处理、自动重试。
"""

import asyncio

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.core.exceptions import EmbeddingException
from app.core.logger import get_logger

logger = get_logger(__name__)


class EmbeddingClient:
    """Embedding 服务客户端 — OpenAI Compatible API"""

    def __init__(self):
        settings = get_settings()
        self.model = settings.EMBEDDING_MODEL
        self.dimensions = settings.EMBEDDING_DIMENSION
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

        self._client = AsyncOpenAI(
            api_key=settings.EMBEDDING_API_KEY or settings.LLM_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
            timeout=60.0,
            max_retries=3,
        )

    async def embed(self, text: str) -> list[float]:
        """单条文本向量化"""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str], max_retries: int = 3) -> list[list[float]]:
        """批量文本向量化（自动分批 + 指数退避重试）"""
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]

            for attempt in range(max_retries):
                try:
                    response = await self._client.embeddings.create(
                        model=self.model,
                        input=batch,
                        dimensions=self.dimensions,
                    )
                    batch_embeddings = [d.embedding for d in response.data]
                    all_embeddings.extend(batch_embeddings)
                    break
                except Exception as e:
                    logger.warning(f"Embedding 失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        raise EmbeddingException(f"Embedding 服务调用失败（已重试 {max_retries} 次）: {e}")
                    await asyncio.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s

        logger.info(f"向量化完成: {len(texts)} 条文本 → {len(all_embeddings)} 个向量")
        return all_embeddings
