"""
BM25 全文检索器

基于 PostgreSQL tsvector + jieba 预分词实现中文 BM25 检索：
- 文档侧：Worker 落库时用 jieba 分词写入 content_segmented，
  search_vector 生成列自动构建 tsvector（'simple' 配置按空格切分）
- 查询侧：查询同样用 jieba 分词，plainto_tsquery 构造查询
- 排序：ts_rank_cd + normalization=32（BM25 近似的文档长度归一化）
"""

import time
from collections.abc import Callable
from uuid import UUID

import jieba
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import get_logger

logger = get_logger(__name__)


class BM25Retriever:
    """BM25 全文检索 — 基于 document_chunks.search_vector"""

    def __init__(self, session_factory: Callable[[], AsyncSession]):
        """
        Args:
            session_factory: 异步会话工厂（如 app.core.database.async_session），
                每次检索创建独立会话，避免跨请求共享连接
        """
        self.session_factory = session_factory

    async def search(self, query: str, kb_id: UUID, limit: int = 50) -> list[dict]:
        """
        BM25 检索

        Args:
            query: 用户查询（内部做 jieba 分词）
            kb_id: 知识库 ID
            limit: 返回数量

        Returns:
            候选文档列表，字段与向量检索对齐：
            id / chunk_id / document_title / content / page_number / score
        """
        start = time.time()

        # jieba 分词，过滤空词与 tsquery 特殊字符
        tokens = [
            w.strip()
            for w in jieba.cut(query)
            if w.strip() and not any(c in w for c in "'\"&|!():*<>")
        ]
        if not tokens:
            return []

        # OR 语义：任一命中即可（中文问句含大量虚词，AND 会全部落空；
        # 排序仍由 ts_rank_cd 保证命中词越多分越高）
        or_query = " | ".join(tokens)

        stmt = text(
            """
            SELECT
                c.id::text AS chunk_id,
                c.content,
                c.page_number,
                d.title AS document_title,
                ts_rank_cd(c.search_vector, to_tsquery('simple', :or_query), 32) AS score
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.kb_id = :kb_id
              AND c.search_vector @@ to_tsquery('simple', :or_query)
              AND d.status = 'COMPLETED'
            ORDER BY score DESC
            LIMIT :limit
            """
        )
        async with self.session_factory() as session:
            result = await session.execute(
                stmt, {"kb_id": str(kb_id), "or_query": or_query, "limit": limit}
            )
            rows = result.mappings().all()

        candidates = [
            {
                "id": row["chunk_id"],
                "chunk_id": row["chunk_id"],
                "document_title": row["document_title"],
                "content": row["content"],
                "page_number": row["page_number"],
                "score": float(row["score"]),
            }
            for row in rows
        ]

        elapsed = (time.time() - start) * 1000
        logger.info(f"BM25 检索完成: {len(candidates)} 条, 耗时 {elapsed:.0f}ms")
        return candidates
