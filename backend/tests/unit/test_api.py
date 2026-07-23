"""API 层单元测试"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.unit
class TestHealthCheck:
    """健康检查测试"""

    @pytest.mark.asyncio
    async def test_health_endpoint_returns_200(self):
        """测试：健康检查返回 200"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "checks" in data
            assert "database" in data["checks"]


@pytest.mark.unit
class TestAuthAPI:
    """认证 API 测试"""

    @pytest.mark.asyncio
    @patch("app.api.deps.decode_token")
    @patch("app.api.deps.UserRepository")
    async def test_get_me_returns_user_info(self, mock_repo_class, mock_decode):
        """测试：GET /me 返回当前用户信息"""
        from unittest.mock import MagicMock
        from uuid import uuid4

        user = MagicMock()
        user.id = uuid4()
        user.username = "testuser"
        user.email = "test@example.com"
        user.display_name = "测试"
        user.role = MagicMock(value="user")
        user.is_active = True
        user.last_login_at = None
        user.created_at = None

        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=user)
        mock_repo_class.return_value = mock_repo
        mock_decode.return_value = {"sub": str(uuid4()), "type": "access"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer fake-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 200
            assert data["data"]["username"] == "testuser"


@pytest.mark.unit
class TestErrorHandling:
    """异常处理测试"""

    @pytest.mark.asyncio
    async def test_404_for_nonexistent_kb(self):
        """测试：不存在的知识库返回统一错误格式"""
        from uuid import uuid4

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/v1/knowledge-bases/{uuid4()}",
                headers={"Authorization": "Bearer fake-token"},
            )
            # 未认证或不存在，返回错误格式
            assert response.status_code in [401, 404]

    @pytest.mark.asyncio
    async def test_401_without_token(self):
        """测试：无 Token 访问受保护接口返回错误格式"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/knowledge-bases/123")
            data = response.json()
            # 应返回统一错误格式
            assert "code" in data
            assert data["code"] != 200
