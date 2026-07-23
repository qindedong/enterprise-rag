"""
检索管线

串联：查询改写 → 检索（向量 / BM25 / 混合）→ 重排序

检索模式：
    vector — 纯向量检索（Qdrant）
    bm25   — 纯全文检索（PostgreSQL tsvector + jieba）
    hybrid — 向量 + BM25，RRF 融合
"""

import time
from uuid import UUID

from app.core.logger import get_logger
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.qdrant_client import QdrantStore
from app.rag.bm25_retriever import BM25Retriever
from app.rag.fusion import rrf_merge
from app.rag.query_rewriter import QueryRewriter
from app.rag.reranker import Reranker

logger = get_logger(__name__)

RETRIEVAL_MODES = ("vector", "bm25", "hybrid")


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
        bm25_retriever: BM25Retriever | None = None,
    ):
        self.embedding_client = embedding_client
        self.qdrant_store = qdrant_store
        self.query_rewriter = query_rewriter
        self.reranker = reranker
        self.bm25_retriever = bm25_retriever

    async def retrieve(
        self,
        question: str,
        kb_id: UUID,
        retrieval_top_k: int | None = None,
        rerank_top_k: int | None = None,
        mode: str = "vector",
        history: list[dict] | None = None,
    ) -> list[dict]:
        """
        执行完整检索流程

        Args:
            question: 用户原始问题
            kb_id: 知识库 ID
            retrieval_top_k: 检索候选数（默认 RETRIEVAL_TOP_K）
            rerank_top_k: 重排后返回数（默认 RERANK_TOP_K）
            mode: 检索模式 vector / bm25 / hybrid
            history: 对话历史（多轮对话时用于指代消解）

        Returns:
            Top-N 相关文档列表
        """
        start = time.time()
        retrieval_top_k = retrieval_top_k or self.RETRIEVAL_TOP_K
        rerank_top_k = rerank_top_k or self.RERANK_TOP_K

        if mode not in RETRIEVAL_MODES:
            raise ValueError(f"不支持的检索模式: {mode}，可选: {RETRIEVAL_MODES}")
        if mode in ("bm25", "hybrid") and self.bm25_retriever is None:
            raise ValueError(f"检索模式 {mode} 需要 BM25Retriever，但管线未配置")

        # Step 1: 查询改写（带历史时做指代消解）
        rewritten = await self.query_rewriter.rewrite(question, history=history)

        # Step 2: 检索候选
        candidates: list[dict] = []

        if mode == "vector":
            candidates = await self._vector_search(rewritten, kb_id, retrieval_top_k)
        elif mode == "bm25":
            candidates = await self.bm25_retriever.search(rewritten, kb_id, limit=retrieval_top_k)
        else:  # hybrid
            vector_results, bm25_results = await self._parallel_search(
                rewritten, kb_id, retrieval_top_k
            )
            candidates = rrf_merge(vector_results, bm25_results)

        if not candidates:
            logger.info(f"检索结果为空 (mode={mode})")
            return []

        # Step 3: 重排序
        top_docs = await self.reranker.rerank(
            query=question,
            candidates=candidates,
            top_k=rerank_top_k,
        )

        elapsed = (time.time() - start) * 1000
        logger.info(
            f"检索完成 (mode={mode}): {len(candidates)} → {len(top_docs)} 条, 耗时 {elapsed:.0f}ms"
        )

        return top_docs

    async def _vector_search(self, query: str, kb_id: UUID, limit: int) -> list[dict]:
        """向量检索"""
        query_vector = await self.embedding_client.embed(query)
        return self.qdrant_store.search(
            query_vector=query_vector,
            kb_id=str(kb_id),
            limit=limit,
        )

    async def _parallel_search(
        self, query: str, kb_id: UUID, limit: int
    ) -> tuple[list[dict], list[dict]]:
        """并行执行向量与 BM25 检索（互不依赖）"""
        import asyncio

        vector_results, bm25_results = await asyncio.gather(
            self._vector_search(query, kb_id, limit),
            self.bm25_retriever.search(query, kb_id, limit=limit),
        )
        return vector_results, bm25_results
