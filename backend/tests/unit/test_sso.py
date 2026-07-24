"""SSO（OIDC）测试 — 授权 URL 构造 + 回调签发 JWT + 自动开通账号"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import UnauthorizedException, ValidationException
from app.main import app
from app.repositories.user_repository import UserRepository
from app.services.oidc_service import OIDCService


def _oidc_settings(enabled=True):
    s = MagicMock()
    s.OIDC_ENABLED = enabled
    s.OIDC_CLIENT_ID = "rag-client"
    s.OIDC_CLIENT_SECRET = "secret"
    s.OIDC_AUTHORIZE_URL = "https://sso.example.com/auth"
    s.OIDC_TOKEN_URL = "https://sso.example.com/token"
    s.OIDC_USERINFO_URL = "https://sso.example.com/userinfo"
    s.OIDC_REDIRECT_URI = "http://localhost:8000/api/v1/auth/sso/callback"
    s.OIDC_SCOPE = "openid email profile"
    return s


@pytest.mark.unit
class TestOIDCService:
    """OIDCService 单元测试"""

    def test_build_authorization_url(self):
        with patch("app.services.oidc_service.get_settings", return_value=_oidc_settings()):
            url = OIDCService().build_authorization_url("state123")
        assert url.startswith("https://sso.example.com/auth?")
        assert "client_id=rag-client" in url
        assert "response_type=code" in url
        assert "state=state123" in url

    def test_disabled_raises(self):
        with patch(
            "app.services.oidc_service.get_settings", return_value=_oidc_settings(enabled=False)
        ):
            with pytest.raises(ValidationException):
                OIDCService().build_authorization_url("s")

    @pytest.mark.asyncio
    async def test_exchange_code_success(self):
        """code → token → userinfo 全流程（mock httpx）"""
        token_resp = MagicMock(status_code=200)
        token_resp.json = lambda: {"access_token": "at-123"}
        userinfo_resp = MagicMock(status_code=200)
        userinfo_resp.json = lambda: {
            "email": "sso@example.com",
            "name": "SSO 用户",
            "sub": "idp-1",
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.get = AsyncMock(return_value=userinfo_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.services.oidc_service.get_settings", return_value=_oidc_settings()),
            patch("app.services.oidc_service.httpx.AsyncClient", return_value=mock_client),
        ):
            info = await OIDCService().exchange_code("code-abc")

        assert info["email"] == "sso@example.com"
        assert info["name"] == "SSO 用户"

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_code(self):
        """IdP 拒绝授权码 → 401"""
        token_resp = MagicMock(status_code=400)
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=token_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with (
            patch("app.services.oidc_service.get_settings", return_value=_oidc_settings()),
            patch("app.services.oidc_service.httpx.AsyncClient", return_value=mock_client),
        ):
            with pytest.raises(UnauthorizedException):
                await OIDCService().exchange_code("bad-code")


@pytest.mark.unit
class TestSSOEndpoints:
    """SSO 端点"""

    @pytest.mark.asyncio
    async def test_login_endpoint_returns_url(self):
        mock_service = MagicMock()
        mock_service.build_authorization_url.return_value = "https://sso.example.com/auth?x=1"
        with patch("app.api.v1.sso.OIDCService", return_value=mock_service):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/auth/sso/login")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["authorization_url"].startswith("https://sso.example.com")
        assert data["state"]

    @pytest.mark.asyncio
    async def test_callback_creates_user_and_issues_jwt(self, db_session: AsyncSession):
        """回调：新邮箱自动开通账号并签发 JWT"""
        email = f"{uuid4().hex[:8]}@sso.com"

        async def _db():
            yield db_session

        app.dependency_overrides[get_db] = _db
        mock_service = MagicMock()
        mock_service.exchange_code = AsyncMock(
            return_value={"email": email, "name": "新用户", "sub": "x"}
        )
        try:
            with patch("app.api.v1.sso.OIDCService", return_value=mock_service):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/v1/auth/sso/callback", params={"code": "c1"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 302
        from urllib.parse import parse_qs, urlparse

        location = resp.headers["location"]
        assert "/sso/callback?" in location
        tokens = parse_qs(urlparse(location).query)
        assert tokens["access_token"][0]
        assert tokens["refresh_token"][0]

        # 用户确实落库
        repo = UserRepository(db_session)
        user = await repo.find_by_email(email)
        assert user is not None
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_callback_existing_user_reused(self, db_session: AsyncSession):
        """已有账号的邮箱不重复创建"""
        repo = UserRepository(db_session)
        existing = await repo.create(
            username=f"u{uuid4().hex[:8]}",
            email=f"{uuid4().hex[:8]}@sso.com",
            hashed_password="x",
        )
        await db_session.commit()

        async def _db():
            yield db_session

        app.dependency_overrides[get_db] = _db
        mock_service = MagicMock()
        mock_service.exchange_code = AsyncMock(
            return_value={"email": existing.email, "name": "任意", "sub": "x"}
        )
        try:
            with patch("app.api.v1.sso.OIDCService", return_value=mock_service):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/api/v1/auth/sso/callback", params={"code": "c1"})
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 302
        assert "/sso/callback?" in resp.headers["location"]
