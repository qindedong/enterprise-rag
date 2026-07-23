"""
Embedding 服务客户端

支持两种模式：
1. 本地模式（默认）：使用 sentence-transformers 本地模型，无需 API Key
2. API 模式：OpenAI Compatible Embedding API

自动根据 EMBEDDING_MODEL 选择模式。
"""

import asyncio
import os

from app.core.config import get_settings
from app.core.exceptions import EmbeddingException
from app.core.logger import get_logger

logger = get_logger(__name__)

# 本地模型缓存
_local_model = None
_local_model_name = None


def _get_local_model(model_name: str):
    """懒加载本地 SentenceTransformer 模型"""
    global _local_model, _local_model_name
    if _local_model is None or _local_model_name != model_name:
        from sentence_transformers import SentenceTransformer

        logger.info(f"正在加载本地 Embedding 模型: {model_name} ...")
        _local_model = SentenceTransformer(model_name)
        _local_model_name = model_name
        logger.info(f"模型加载完成，向量维度: {_local_model.get_sentence_embedding_dimension()}")
    return _local_model


class EmbeddingClient:
    """
    Embedding 服务客户端

    优先使用本地模型（sentence-transformers），
    如果配置了 EMBEDDING_API_KEY 则使用远程 API。
    """

    # 本地模型名称（通过环境变量 EMBEDDING_LOCAL_MODEL 自定义）
    LOCAL_MODEL = os.environ.get("EMBEDDING_LOCAL_MODEL", "BAAI/bge-small-zh-v1.5")

    def __init__(self):
        settings = get_settings()
        self.model = settings.EMBEDDING_MODEL
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

        # 判断是否有远程 API Key（必须显式配置 EMBEDDING_API_KEY，不复用 LLM_API_KEY）
        api_key = settings.EMBEDDING_API_KEY
        use_local = not api_key or not api_key.strip()

        if use_local:
            self._client = None
            self._use_local = True
            self._local_dim = None
            logger.info(f"Embedding 使用本地模型: {self.LOCAL_MODEL}")
        else:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=settings.EMBEDDING_BASE_URL or settings.LLM_BASE_URL,
                timeout=60.0,
                max_retries=3,
            )
            self._use_local = False
            self.dimensions = settings.EMBEDDING_DIMENSION
            logger.info(f"Embedding 使用远程 API: {settings.EMBEDDING_BASE_URL}")

    async def embed(self, text: str) -> list[float]:
        """单条文本向量化"""
        embeddings = await self.embed_batch([text])
        return embeddings[0]

    async def embed_batch(self, texts: list[str], max_retries: int = 3) -> list[list[float]]:
        """批量文本向量化"""
        if self._use_local:
            return await self._embed_local(texts)
        else:
            return await self._embed_remote(texts, max_retries)

    async def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """本地模型向量化（在独立线程中运行，避免阻塞事件循环）"""
        import concurrent.futures

        model = _get_local_model(self.LOCAL_MODEL)

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            embeddings = await loop.run_in_executor(
                pool, lambda: model.encode(texts, normalize_embeddings=True).tolist()
            )

        logger.info(f"本地向量化完成: {len(texts)} 条, 维度: {len(embeddings[0])}")
        return embeddings

    async def _embed_remote(self, texts: list[str], max_retries: int) -> list[list[float]]:
        """远程 API 向量化"""
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]

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
                        raise EmbeddingException(
                            f"Embedding 服务调用失败（已重试 {max_retries} 次）: {e}"
                        ) from e
                    await asyncio.sleep(2**attempt)

        logger.info(f"远程向量化完成: {len(texts)} 条 → {len(all_embeddings)} 个向量")
        return all_embeddings
