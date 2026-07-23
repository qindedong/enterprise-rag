"""Service 层补充测试 — KBService 边界, ConversationService 边界, AuthService"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
    ValidationException,
)
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.kb_service import KBService


@pytest.mark.unit
class TestKBServiceExtended:
    """KBService 边界测试"""

    @pytest.mark.asyncio
    async def test_list_by_user(self):
        """测试：list_by_user"""
        kb_repo = AsyncMock()
        mock_kb = MagicMock()
        mock_kb.id = uuid4()
        mock_kb.name = "test"
        mock_kb.description = ""
        mock_kb.owner_id = uuid4()
        mock_kb.status = MagicMock(value="active")
        mock_kb.created_at = None
        mock_kb.updated_at = None
        kb_repo.list_by_user = AsyncMock(return_value=([mock_kb], 1))

        service = KBService(kb_repo)
        items, total = await service.list_by_user(uuid4())

        assert total == 1
        assert len(items) == 1

    @pytest.mark.asyncio
    async def test_update_with_no_changes(self):
        """测试：owner 更新但无变化字段"""
        owner_id = uuid4()
        kb_repo = AsyncMock()
        mock_kb = MagicMock()
        mock_kb.id = uuid4()
        mock_kb.owner_id = owner_id
        kb_repo.find_by_id = AsyncMock(return_value=mock_kb)

        mock_updated = MagicMock()
        mock_updated.id = mock_kb.id
        mock_updated.name = "old_name"
        mock_updated.description = ""
        mock_updated.owner_id = owner_id
        mock_updated.status = MagicMock(value="active")
        mock_updated.created_at = None
        mock_updated.updated_at = None
        kb_repo.find_by_id = AsyncMock(return_value=mock_updated)

        service = KBService(kb_repo)
        result = await service.update(mock_kb.id, owner_id)
        assert result is not None

    @pytest.mark.asyncio
    async def test_remove_member_self(self):
        """测试：不能移除所有者自身"""
        owner_id = uuid4()
        kb_repo = AsyncMock()
        mock_kb = MagicMock()
        mock_kb.owner_id = owner_id
        kb_repo.find_by_id = AsyncMock(return_value=mock_kb)

        service = KBService(kb_repo)
        with pytest.raises(ValidationException):
            await service.remove_member(uuid4(), owner_id, owner_id)

    @pytest.mark.asyncio
    async def test_list_members_no_access(self):
        """测试：无权访问成员列表"""
        kb_repo = AsyncMock()
        kb_repo.is_member = AsyncMock(return_value=False)

        service = KBService(kb_repo)
        with pytest.raises(ForbiddenException):
            await service.list_members(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_get_detail_no_access(self):
        """测试：无权访问知识库详情"""
        kb_repo = AsyncMock()
        mock_kb = MagicMock()
        mock_kb.id = uuid4()
        mock_kb.owner = None
        kb_repo.find_by_id_with_owner = AsyncMock(return_value=mock_kb)
        kb_repo.is_member = AsyncMock(return_value=False)

        service = KBService(kb_repo)
        with pytest.raises(ForbiddenException):
            await service.get_detail(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_update_kb_not_found_for_member_op(self):
        """测试：操作不存在的知识库"""
        kb_repo = AsyncMock()
        kb_repo.find_by_id = AsyncMock(return_value=None)

        service = KBService(kb_repo)
        with pytest.raises(NotFoundException):
            await service.add_member(uuid4(), uuid4(), uuid4(), "viewer")


@pytest.mark.unit
class TestAuthServiceExtended:
    """AuthService 边界测试"""

    @pytest.mark.asyncio
    async def test_login_user_not_found(self):
        """测试：用户不存在"""
        user_repo = AsyncMock()
        user_repo.find_by_email = AsyncMock(return_value=None)

        service = AuthService(user_repo)
        with pytest.raises(UnauthorizedException):
            await service.login("nobody@test.com", "any_password")


@pytest.mark.unit
class TestConversationServiceExtended:
    """ConversationService 边界测试"""

    @pytest.mark.asyncio
    async def test_list_by_user_with_kb_filter(self):
        """测试：按知识库筛选对话列表"""
        conv_repo = AsyncMock()
        conv_repo.list_by_user = AsyncMock(return_value=([], 0))

        service = ConversationService(conv_repo, AsyncMock())
        _items, total = await service.list_by_user(uuid4(), kb_id=uuid4())

        assert total == 0
        conv_repo.list_by_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_feedback(self):
        """测试：设置消息反馈"""
        msg_repo = AsyncMock()
        msg_repo.set_feedback = AsyncMock(return_value=None)

        service = ConversationService(AsyncMock(), msg_repo)
        await service.set_feedback(uuid4(), "positive", "有帮助")

        msg_repo.set_feedback.assert_called_once()
