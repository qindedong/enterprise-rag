"""RAG 管线与重排序器单元测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.rag.pipeline import RetrievalPipeline
from app.rag.reranker import Reranker
from app.prompts.registry import PromptRegistry, PromptTemplate


@pytest.mark.unit
class TestReranker:
    """Reranker 测试"""

    @pytest.mark.asyncio
    async def test_rerank_sorts_by_score(self):
        """测试：按 score 降序排列"""
        reranker = Reranker()
        candidates = [
            {"id": "1", "score": 0.5, "content": "aa"},
            {"id": "2", "score": 0.9, "content": "bb"},
            {"id": "3", "score": 0.7, "content": "cc"},
        ]
        result = await reranker.rerank("query", candidates, top_k=3)
        assert result[0]["score"] == 0.9
        assert result[1]["score"] == 0.7
        assert result[2]["score"] == 0.5

    @pytest.mark.asyncio
    async def test_rerank_empty_candidates(self):
        """测试：空候选列表返回空"""
        reranker = Reranker()
        result = await reranker.rerank("query", [], top_k=10)
        assert result == []

    @pytest.mark.asyncio
    async def test_rerank_respects_top_k(self):
        """测试：只返回 top_k 条"""
        reranker = Reranker()
        candidates = [
            {"id": str(i), "score": float(i) / 100, "content": f"text_{i}"}
            for i in range(20)
        ]
        result = await reranker.rerank("query", candidates, top_k=5)
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_diversity_filter_removes_duplicates(self):
        """测试：多样性过滤去重"""
        reranker = Reranker()
        candidates = [
            {"id": "1", "score": 0.9, "content": "完全相同的文档"},
            {"id": "2", "score": 0.8, "content": "完全相同的文档"},  # 相同内容
            {"id": "3", "score": 0.7, "content": "不同的文档"},       # 不同内容
        ]
        result = await reranker.rerank("query", candidates, top_k=5)
        # 重复的被过滤
        assert len(result) <= 2


@pytest.mark.unit
class TestRetrievalPipeline:
    """RetrievalPipeline 测试"""

    @pytest.mark.asyncio
    async def test_retrieve_empty_result(self):
        """测试：检索不到结果返回空"""
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 512)

        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = []

        mock_rewriter = AsyncMock()
        mock_rewriter.rewrite = AsyncMock(return_value="改写后的查询")

        mock_reranker = AsyncMock()
        mock_reranker.rerank = AsyncMock(return_value=[])

        pipeline = RetrievalPipeline(mock_embedding, mock_qdrant, mock_rewriter, mock_reranker)
        result = await pipeline.retrieve("问题", uuid4())

        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_returns_top10(self):
        """测试：正常检索返回 Top-10 结果"""
        mock_embedding = AsyncMock()
        mock_embedding.embed = AsyncMock(return_value=[0.1] * 512)

        candidates = [
            {"id": str(i), "score": 0.9 - i * 0.01, "content": f"doc_{i}", "document_title": f"文件_{i}"}
            for i in range(50)
        ]
        mock_qdrant = MagicMock()
        mock_qdrant.search.return_value = candidates

        mock_rewriter = AsyncMock()
        mock_rewriter.rewrite = AsyncMock(return_value="改写查询")

        top10 = candidates[:10]
        mock_reranker = AsyncMock()
        mock_reranker.rerank = AsyncMock(return_value=top10)

        pipeline = RetrievalPipeline(mock_embedding, mock_qdrant, mock_rewriter, mock_reranker)
        result = await pipeline.retrieve("用户问题", uuid4())

        assert len(result) == 10
        # 验证检索参数
        mock_qdrant.search.assert_called_once()
        call_args = mock_qdrant.search.call_args.kwargs
        assert call_args["limit"] == 50

