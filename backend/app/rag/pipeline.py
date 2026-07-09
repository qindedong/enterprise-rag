"""
检索管线

串联：查询改写 → 向量检索 → 重排序
"""

import time
from uuid import UUID

from app.core.logger import get_logger
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.qdrant_client import QdrantStore
from app.rag.query_rewriter import QueryRewriter
from app.rag.reranker import Reranker

logger = get_logger(__name__)


class RetrievalPipeline:
    """检索管线 — 从查询到候选文档"""

    RETRIEVAL_TOP_K: int = 50
    RERANK_TOP_K: int = 10

    def __init__(
        self,
        embedding_client: EmbeddingClient,
        qdrant_store: QdrantStore,
        query_rewriter: QueryRewriter,
        reranker: Reranker,
    ):
        self.embedding_client = embedding_client
        self.qdrant_store = qdrant_store
        self.query_rewriter = query_rewriter
        self.reranker = reranker

    async def retrieve(self, question: str, kb_id: UUID) -> list[dict]:
        """
        执行完整检索流程

        Args:
            question: 用户原始问题
            kb_id: 知识库 ID

        Returns:
            Top-10 相关文档列表
        """
        start = time.time()

        # Step 1: 查询改写
        rewritten = await self.query_rewriter.rewrite(question)

        # Step 2: 向量化查询
        query_vector = await self.embedding_client.embed(rewritten)

        # Step 3: Qdrant 检索 — Top-50
        candidates = self.qdrant_store.search(
            query_vector=query_vector,
            kb_id=str(kb_id),
            limit=self.RETRIEVAL_TOP_K,
        )

        if not candidates:
            logger.info("检索结果为空")
            return []

        # Step 4: 重排序 — Top-10
        top_docs = await self.reranker.rerank(
            query=question,
            candidates=candidates,
            top_k=self.RERANK_TOP_K,
        )

        elapsed = (time.time() - start) * 1000
        logger.info(f"检索完成: {len(candidates)} → {len(top_docs)} 条, 耗时 {elapsed:.0f}ms")

        return top_docs
