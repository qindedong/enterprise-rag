"""API 层补充测试"""

import pytest


@pytest.mark.unit
class TestRAGAPI:
    """RAG 问答 API 测试"""

    @pytest.mark.asyncio
    async def test_chat_sync_returns_error_without_kb(self, client, override_get_db):
        """测试：不存在的知识库返回 404"""
        from uuid import uuid4

        response = await client.post(
            f"/api/v1/knowledge-bases/{uuid4()}/chat/sync",
            json={"question": "答案是多少？"},
        )
        assert response.status_code == 404
        data = response.json()
        assert data["code"] == 404


@pytest.mark.unit
class TestAuthAPI:
    """认证 API 扩展测试"""

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client, override_get_db):
        """测试：无效 refresh token 返回 401"""
        response = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid-token-string-xxxxx"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_openapi_docs_accessible(self, client, override_get_db):
        """测试：OpenAPI 文档可访问"""
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_health_check(self, client, override_get_db):
        """测试：健康检查可用"""
        response = await client.get("/health")
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
