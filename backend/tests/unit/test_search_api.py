"""独立检索 API（POST /search）单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.main import app


def _mock_rag_service(docs: list[dict]) -> MagicMock:
    """构造 mock 的 RAGService（仅检索管线部分）"""
    service = MagicMock()
    service.retrieval = MagicMock()
    service.retrieval.retrieve = AsyncMock(return_value=docs)
    return service


def _fake_docs(n: int = 2) -> list[dict]:
    return [
        {
            "chunk_id": f"chunk-{i}",
            "document_title": f"文档{i}",
            "content": f"内容片段{i}",
            "page_number": i,
            "score": 0.9 - i * 0.1,
        }
        for i in range(n)
    ]


@pytest.fixture()
def auth_override():
    """以 super_admin 身份绕过 RBAC 成员校验（RBAC 本身由 test_rbac.py 覆盖）"""
    user = MagicMock()
    user.id = uuid4()
    user.role = "super_admin"
    app.dependency_overrides[get_current_user] = lambda: user
    yield
    app.dependency_overrides.clear()


@pytest.mark.unit
class TestSearchAPI:
    """POST /api/v1/knowledge-bases/{kb_id}/search"""

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_search_returns_results(
        self, mock_kb_repo_class, mock_get_service, auth_override
    ):
        """测试：检索返回结构化结果"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo
        mock_get_service.return_value = _mock_rag_service(_fake_docs(2))

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{kb.id}/search",
                json={"question": "如何申请年假？"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        payload = data["data"]
        assert payload["mode"] == "vector"
        assert payload["total"] == 2
        assert payload["results"][0]["rank"] == 1
        assert payload["results"][0]["chunk_id"] == "chunk-0"
        assert "processing_time_ms" in payload

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_search_passes_top_k_params(
        self, mock_kb_repo_class, mock_get_service, auth_override
    ):
        """测试：top_k / candidate_k 参数传递给检索管线"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo
        service = _mock_rag_service(_fake_docs(1))
        mock_get_service.return_value = service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{kb.id}/search",
                json={"question": "测试", "top_k": 5, "candidate_k": 30},
            )

        assert response.status_code == 200
        service.retrieval.retrieve.assert_called_once()
        _, kwargs = service.retrieval.retrieve.call_args
        assert kwargs["retrieval_top_k"] == 30
        assert kwargs["rerank_top_k"] == 5

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_search_empty_results(self, mock_kb_repo_class, mock_get_service, auth_override):
        """测试：检索结果为空时返回空列表"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo
        mock_get_service.return_value = _mock_rag_service([])

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{kb.id}/search",
                json={"question": "不存在的内容"},
            )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["total"] == 0
        assert payload["results"] == []

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_search_hybrid_mode_supported(
        self, mock_kb_repo_class, mock_get_service, auth_override
    ):
        """测试：hybrid 模式透传给检索管线"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo
        service = _mock_rag_service(_fake_docs(1))
        mock_get_service.return_value = service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{kb.id}/search",
                json={"question": "测试", "mode": "hybrid"},
            )

        assert response.status_code == 200
        _, kwargs = service.retrieval.retrieve.call_args
        assert kwargs["mode"] == "hybrid"

    @pytest.mark.asyncio
    @patch("app.api.v1.rag._get_rag_service")
    @patch("app.core.rbac.KBRepository")
    async def test_search_pipeline_value_error_returns_422(
        self, mock_kb_repo_class, mock_get_service, auth_override
    ):
        """测试：管线拒绝的模式返回校验错误"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo
        service = _mock_rag_service([])
        service.retrieval.retrieve = AsyncMock(side_effect=ValueError("不支持的检索模式"))
        mock_get_service.return_value = service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{kb.id}/search",
                json={"question": "测试", "mode": "hybrid"},
            )

        assert response.status_code == 422
        data = response.json()
        assert data["code"] != 200

    @pytest.mark.asyncio
    @patch("app.core.rbac.KBRepository")
    async def test_search_kb_not_found(self, mock_kb_repo_class, auth_override):
        """测试：知识库不存在返回 404"""
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)
        mock_kb_repo_class.return_value = mock_repo

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{uuid4()}/search",
                json={"question": "测试"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    @patch("app.core.rbac.KBRepository")
    async def test_search_invalid_mode_rejected_by_schema(self, mock_kb_repo_class, auth_override):
        """测试：非法 mode 被请求模型拒绝（422）"""
        kb = MagicMock()
        kb.id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=kb)
        mock_kb_repo_class.return_value = mock_repo

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/api/v1/knowledge-bases/{uuid4()}/search",
                json={"question": "测试", "mode": "semantic"},
            )

        assert response.status_code == 422
