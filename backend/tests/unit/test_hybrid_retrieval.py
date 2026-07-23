"""混合检索单元测试：RRF 融合 + BM25 检索器 + Pipeline 模式路由"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.rag.fusion import rrf_merge
from app.rag.pipeline import RetrievalPipeline


def _doc(chunk_id: str, score: float = 0.9, title: str = "文档") -> dict:
    return {
        "chunk_id": chunk_id,
        "document_title": title,
        "content": f"内容-{chunk_id}",
        "score": score,
    }


@pytest.mark.unit
class TestRRFMerge:
    """RRF 融合算法"""

    def test_both_lists_hit_ranks_first(self):
        """两路都命中的文档应排在只在单路命中的文档之前"""
        vector = [_doc("a"), _doc("b"), _doc("c")]
        bm25 = [_doc("b"), _doc("d"), _doc("a")]

        merged = rrf_merge(vector, bm25)

        ids = [d["chunk_id"] for d in merged]
        # a: 1/61+1/63, b: 1/62+1/61, c: 1/63, d: 1/62
        # b 两路都命中且名次高 → 第一
        assert ids[0] == "b"
        assert set(ids) == {"a", "b", "c", "d"}
        # 双路命中的 a、b 应高于单路的 c、d
        assert ids.index("a") < ids.index("c")
        assert ids.index("b") < ids.index("d")

    def test_score_is_rrf_sum(self):
        """RRF 分数 = Σ 1/(60+rank)"""
        merged = rrf_merge([_doc("x"), _doc("y")], k=60)
        assert merged[0]["chunk_id"] == "x"
        assert merged[0]["score"] == pytest.approx(1 / 61)
        assert merged[1]["score"] == pytest.approx(1 / 62)

    def test_empty_lists(self):
        assert rrf_merge() == []
        assert rrf_merge([], []) == []

    def test_rrf_detail_records_ranks(self):
        """rrf_detail 记录各路名次"""
        merged = rrf_merge([_doc("a")], [_doc("a"), _doc("b")])
        a = next(d for d in merged if d["chunk_id"] == "a")
        assert a["rrf_detail"] == {0: 1, 1: 1}


@pytest.mark.unit
class TestBM25Retriever:
    """BM25 检索器（SQL 交互用 mock）"""

    @pytest.mark.asyncio
    async def test_search_returns_aligned_fields(self):
        """返回字段与向量检索对齐"""
        from app.rag.bm25_retriever import BM25Retriever

        row = {
            "chunk_id": "c1",
            "content": "年假 5 天",
            "page_number": 2,
            "document_title": "考勤制度",
            "score": 0.42,
        }
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [row]

        session = AsyncMock()
        session.execute = AsyncMock(return_value=mock_result)
        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = AsyncMock(return_value=False)

        retriever = BM25Retriever(factory)
        results = await retriever.search("年假有几天", uuid4(), limit=10)

        assert len(results) == 1
        r = results[0]
        assert r["chunk_id"] == "c1"
        assert r["document_title"] == "考勤制度"
        assert r["score"] == pytest.approx(0.42)
        # SQL 参数：jieba 分词结果应以 OR 连接传入
        args = session.execute.call_args[0]
        assert " | " in args[1]["or_query"]  # 分词后以 OR 连接

    @pytest.mark.asyncio
    async def test_blank_query_returns_empty(self):
        from app.rag.bm25_retriever import BM25Retriever

        factory = MagicMock()
        retriever = BM25Retriever(factory)
        assert await retriever.search("   ", uuid4()) == []
        factory.assert_not_called()


@pytest.mark.unit
class TestPipelineModes:
    """RetrievalPipeline 的 mode 路由"""

    def _make_pipeline(self) -> RetrievalPipeline:
        embedding = MagicMock()
        embedding.embed = AsyncMock(return_value=[0.1] * 512)
        qdrant = MagicMock()
        qdrant.search = MagicMock(return_value=[_doc("v1"), _doc("v2")])
        rewriter = MagicMock()
        rewriter.rewrite = AsyncMock(side_effect=lambda q, history=None: q)
        reranker = MagicMock()
        reranker.rerank = AsyncMock(side_effect=lambda query, candidates, top_k: candidates[:top_k])
        bm25 = MagicMock()
        bm25.search = AsyncMock(return_value=[_doc("b1"), _doc("v2", title="BM25文档")])
        return RetrievalPipeline(embedding, qdrant, rewriter, reranker, bm25)

    @pytest.mark.asyncio
    async def test_vector_mode_only_calls_qdrant(self):
        pipeline = self._make_pipeline()
        docs = await pipeline.retrieve("测试", uuid4(), mode="vector")
        pipeline.qdrant_store.search.assert_called_once()
        pipeline.bm25_retriever.search.assert_not_called()
        assert [d["chunk_id"] for d in docs] == ["v1", "v2"]

    @pytest.mark.asyncio
    async def test_bm25_mode_only_calls_bm25(self):
        pipeline = self._make_pipeline()
        docs = await pipeline.retrieve("测试", uuid4(), mode="bm25")
        pipeline.bm25_retriever.search.assert_called_once()
        pipeline.qdrant_store.search.assert_not_called()
        assert docs[0]["chunk_id"] == "b1"

    @pytest.mark.asyncio
    async def test_hybrid_mode_fuses_both(self):
        pipeline = self._make_pipeline()
        docs = await pipeline.retrieve("测试", uuid4(), mode="hybrid")
        pipeline.qdrant_store.search.assert_called_once()
        pipeline.bm25_retriever.search.assert_called_once()
        ids = {d["chunk_id"] for d in docs}
        assert ids == {"v1", "v2", "b1"}
        # v2 双路命中 → 应排第一
        assert docs[0]["chunk_id"] == "v2"

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self):
        pipeline = self._make_pipeline()
        with pytest.raises(ValueError, match="不支持的检索模式"):
            await pipeline.retrieve("测试", uuid4(), mode="semantic")

    @pytest.mark.asyncio
    async def test_hybrid_without_bm25_raises(self):
        pipeline = self._make_pipeline()
        pipeline.bm25_retriever = None
        with pytest.raises(ValueError, match="BM25Retriever"):
            await pipeline.retrieve("测试", uuid4(), mode="hybrid")
