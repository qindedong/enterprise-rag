"""跨知识库检索/问答测试 — RAGService.retrieve_multi + /search/multi + /chat/multi/sync"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.main import app
from app.services.rag_service import RAGService


def _doc(kb: str, score: float, n: int = 0) -> dict:
    return {
        "chunk_id": f"{kb}-chunk-{n}",
        "document_title": f"{kb}文档",
        "content": f"{kb}内容",
        "score": score,
    }


@pytest.fixture()
def auth_override():
    """以 super_admin 身份绕过 RBAC 成员校验"""
    user = MagicMock()
    user.id = uuid4()
    user.role = "super_admin"
    app.dependency_overrides[get_current_user] = lambda: user
    yield
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestRetrieveMulti:
    """RAGService.retrieve_multi 归并逻辑"""

    @pytest.mark.asyncio
    async def test_merge_sorted_by_score_and_tagged(self):
        """多库结果按分数归并排序，并标记来源 kb_id"""
        kb1, kb2 = uuid4(), uuid4()
        pipeline = MagicMock()

        async def fake_retrieve(question, kb_id, **kwargs):
            if kb_id == kb1:
                return [_doc("A", 0.7), _doc("A", 0.5, 1)]
            return [_doc("B", 0.9)]

        pipeline.retrieve = AsyncMock(side_effect=fake_retrieve)
        service = RAGService(pipeline, MagicMock())

        docs = await service.retrieve_multi("问题", [kb1, kb2], top_k=10)
        assert [d["score"] for d in docs] == [0.9, 0.7, 0.5]
        assert docs[0]["kb_id"] == str(kb2)
        assert docs[1]["kb_id"] == str(kb1)

    @pytest.mark.asyncio
    async def test_top_k_truncation(self):
        """归并后按 top_k 截断"""
        kb1, kb2 = uuid4(), uuid4()
        pipeline = MagicMock()
        pipeline.retrieve = AsyncMock(return_value=[_doc("A", 0.9), _doc("A", 0.8, 1)])
        service = RAGService(pipeline, MagicMock())

        docs = await service.retrieve_multi("问题", [kb1, kb2], top_k=3)
        assert len(docs) == 3

    @pytest.mark.asyncio
    async def test_single_kb_failure_tolerated(self):
        """单库检索失败不影响其他库"""
        kb1, kb2 = uuid4(), uuid4()
        pipeline = MagicMock()

        async def fake_retrieve(question, kb_id, **kwargs):
            if kb_id == kb1:
                raise RuntimeError("Qdrant 挂了")
            return [_doc("B", 0.9)]

        pipeline.retrieve = AsyncMock(side_effect=fake_retrieve)
        service = RAGService(pipeline, MagicMock())

        docs = await service.retrieve_multi("问题", [kb1, kb2])
        assert len(docs) == 1
        assert docs[0]["kb_id"] == str(kb2)


@pytest.mark.unit
class TestMultiSearchAPI:
    """POST /api/v1/search/multi"""

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_multi_search_returns_results(
        self, mock_kb_repo_class, mock_get_service, auth_override
    ):
        """跨库检索返回带来源标记的结果"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo

        service = MagicMock()
        service.retrieve_multi = AsyncMock(return_value=[_doc("A", 0.9), _doc("B", 0.8)])
        mock_get_service.return_value = service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search/multi",
                json={"question": "考勤制度", "kb_ids": [str(uuid4()), str(uuid4())]},
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert data["mode"] == "hybrid"
        assert len(data["kb_ids"]) == 2
        assert data["results"][0]["rank"] == 1

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_multi_chat_sync(self, mock_kb_repo_class, mock_get_service, auth_override):
        """跨库问答返回答案与引用"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo

        service = MagicMock()
        service.ask_multi = AsyncMock(
            return_value={
                "answer": "答案 [1]",
                "citations": [{"index": 1, "document_title": "A文档"}],
                "token_usage": {},
                "processing_time_ms": 100,
            }
        )
        mock_get_service.return_value = service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/chat/multi/sync",
                json={"question": "考勤制度", "kb_ids": [str(uuid4())]},
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["answer"] == "答案 [1]"
        assert len(data["citations"]) == 1

    @pytest.mark.asyncio
    async def test_multi_search_schema_rejects_empty_kb_ids(self, auth_override):
        """kb_ids 为空被请求模型拒绝"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/search/multi",
                json={"question": "测试", "kb_ids": []},
            )
        assert resp.status_code == 422
