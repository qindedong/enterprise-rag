"""API Key 测试 — 创建/列表/吊销 + API Key 认证链路"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import _hash_api_key, get_current_user, get_db
from app.main import app
from app.repositories.api_key_repository import APIKeyRepository
from app.repositories.user_repository import UserRepository


async def _create_user(db_session: AsyncSession):
    repo = UserRepository(db_session)
    user = await repo.create(
        username=f"u{uuid4().hex[:8]}",
        email=f"{uuid4().hex[:8]}@test.com",
        hashed_password="x",
    )
    await db_session.commit()
    return user


def _override_db(db_session):
    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db


@pytest.mark.unit
class TestAPIKeyManagement:
    """API Key 管理接口"""

    @pytest.mark.asyncio
    async def test_create_list_revoke_flow(self, db_session: AsyncSession):
        """创建（返回明文一次）→ 列表（脱敏）→ 吊销"""
        user = await _create_user(db_session)
        _override_db(db_session)
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 创建
                resp = await client.post("/api/v1/api-keys", json={"name": "CI 集成"})
                assert resp.status_code == 201
                data = resp.json()["data"]
                assert data["api_key"].startswith("rag_")
                assert data["masked_key"].endswith("••••••••")
                key_id = data["id"]

                # 列表（不含明文）
                resp = await client.get("/api/v1/api-keys")
                assert resp.status_code == 200
                items = resp.json()["data"]
                assert len(items) == 1
                assert "api_key" not in items[0]
                assert items[0]["is_active"] is True

                # 吊销
                resp = await client.delete(f"/api/v1/api-keys/{key_id}")
                assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

        # 吊销后认证应失败
        repo = APIKeyRepository(db_session)
        key = await repo.find_by_id(UUID(key_id))
        assert key.is_active is False

    @pytest.mark.asyncio
    async def test_cannot_revoke_others_key(self, db_session: AsyncSession):
        """不能吊销别人的 Key"""
        owner = await _create_user(db_session)
        other = await _create_user(db_session)

        repo = APIKeyRepository(db_session)
        key = await repo.create(owner.id, "测试", "rag_test1234", _hash_api_key("rag_test1234x"))
        await db_session.commit()

        _override_db(db_session)
        app.dependency_overrides[get_current_user] = lambda: other
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.delete(f"/api/v1/api-keys/{key.id}")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()


@pytest.mark.unit
class TestAPIKeyAuth:
    """API Key 认证（真实 get_current_user 链路）"""

    @pytest.mark.asyncio
    async def test_x_api_key_header_authenticates(self, db_session: AsyncSession):
        """X-API-Key 头可访问受保护接口"""
        user = await _create_user(db_session)
        raw_key = f"rag_{uuid4().hex}"
        repo = APIKeyRepository(db_session)
        await repo.create(user.id, "测试", raw_key[:12], _hash_api_key(raw_key))
        await db_session.commit()

        _override_db(db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/analytics/overview",
                    headers={"X-API-Key": raw_key},
                )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_bearer_api_key_authenticates(self, db_session: AsyncSession):
        """Bearer rag_ 前缀 Token 按 API Key 认证"""
        user = await _create_user(db_session)
        raw_key = f"rag_{uuid4().hex}"
        repo = APIKeyRepository(db_session)
        await repo.create(user.id, "测试", raw_key[:12], _hash_api_key(raw_key))
        await db_session.commit()

        _override_db(db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/analytics/overview",
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
            assert resp.status_code == 200
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_invalid_api_key_rejected(self, db_session: AsyncSession):
        """无效 Key 返回 401"""
        _override_db(db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/analytics/overview",
                    headers={"X-API-Key": "rag_not_exists_key"},
                )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_expired_api_key_rejected(self, db_session: AsyncSession):
        """过期 Key 返回 401"""
        user = await _create_user(db_session)
        raw_key = f"rag_{uuid4().hex}"
        repo = APIKeyRepository(db_session)
        await repo.create(
            user.id,
            "过期",
            raw_key[:12],
            _hash_api_key(raw_key),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        await db_session.commit()

        _override_db(db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    "/api/v1/analytics/overview",
                    headers={"X-API-Key": raw_key},
                )
            assert resp.status_code == 401
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_last_used_at_updated(self, db_session: AsyncSession):
        """认证成功后更新最近使用时间"""
        user = await _create_user(db_session)
        raw_key = f"rag_{uuid4().hex}"
        repo = APIKeyRepository(db_session)
        key = await repo.create(user.id, "测试", raw_key[:12], _hash_api_key(raw_key))
        await db_session.commit()

        _override_db(db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/api/v1/analytics/overview", headers={"X-API-Key": raw_key})
        finally:
            app.dependency_overrides.clear()

        await db_session.refresh(key)
        assert key.last_used_at is not None
