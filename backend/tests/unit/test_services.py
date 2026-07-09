"""认证与知识库模块单元测试"""

import pytest
from unittest.mock import AsyncMock, patch

from app.services.auth_service import AuthService
from app.services.kb_service import KBService
from app.core.exceptions import DuplicateException, UnauthorizedException, NotFoundException


@pytest.mark.unit
class TestAuthService:
    """认证服务测试"""

    @pytest.mark.asyncio
    @patch("app.services.auth_service.hash_password")
    async def test_register_success(self, mock_hash, db_session):
        """测试：注册成功"""
        mock_hash.return_value = "$2b$12$hashed_mock_value_here_abcdefghijklmnopqrstuv"
        user_repo = AsyncMock()
        user_repo.find_by_username.return_value = None
        user_repo.find_by_email.return_value = None

        service = AuthService(user_repo)
        user = await service.register("testuser", "test@example.com", "SecureP123")

        assert user_repo.create.called

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, db_session):
        """测试：用户名重复"""
        user_repo = AsyncMock()
        user_repo.find_by_username.return_value = AsyncMock()
        user_repo.find_by_email.return_value = None

        service = AuthService(user_repo)
        with pytest.raises(DuplicateException, match="用户名"):
            await service.register("testuser", "test@example.com", "SecureP@ss123")

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, db_session):
        """测试：邮箱重复"""
        user_repo = AsyncMock()
        user_repo.find_by_username.return_value = None
        user_repo.find_by_email.return_value = AsyncMock()

        service = AuthService(user_repo)
        with pytest.raises(DuplicateException, match="邮箱"):
            await service.register("testuser", "test@example.com", "SecureP@ss123")

    @pytest.mark.asyncio
    async def test_login_invalid_email(self, db_session):
        """测试：邮箱不存在"""
        user_repo = AsyncMock()
        user_repo.find_by_email.return_value = None

        service = AuthService(user_repo)
        with pytest.raises(UnauthorizedException):
            await service.login("bad@example.com", "password")


@pytest.mark.unit
class TestKBService:
    """知识库服务测试"""

    @pytest.mark.asyncio
    async def test_create_success(self, db_session):
        """测试：创建知识库成功"""
        from uuid import uuid4

        kb_repo = AsyncMock()
        kb_repo.find_by_name_and_owner.return_value = None

        service = KBService(kb_repo)
        result = await service.create(name="测试知识库", owner_id=uuid4())

        assert kb_repo.create.called

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, db_session):
        """测试：知识库名称重复"""
        from uuid import uuid4

        kb_repo = AsyncMock()
        kb_repo.find_by_name_and_owner.return_value = AsyncMock()

        service = KBService(kb_repo)
        with pytest.raises(DuplicateException):
            await service.create(name="重复库", owner_id=uuid4())

    @pytest.mark.asyncio
    async def test_create_invalid_chunk_size(self, db_session):
        """测试：分块大小超出范围"""
        from uuid import uuid4

        kb_repo = AsyncMock()
        kb_repo.find_by_name_and_owner.return_value = None

        service = KBService(kb_repo)
        with pytest.raises(Exception):  # ValidationException
            await service.create(name="测试", owner_id=uuid4(), chunk_size=100)

    @pytest.mark.asyncio
    async def test_delete_kb_not_found(self, db_session):
        """测试：删除不存在的知识库"""
        from uuid import uuid4

        kb_repo = AsyncMock()
        kb_repo.find_by_id.return_value = None

        service = KBService(kb_repo)
        with pytest.raises(NotFoundException):
            await service.delete(kb_id=uuid4(), user_id=uuid4())
