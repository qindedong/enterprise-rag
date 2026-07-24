"""RBAC 权限控制测试 — check_kb_permission / require_kb_role / require_role"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.rbac import check_kb_permission, require_role
from app.models.database.knowledge_base import MemberRole
from app.models.database.user import UserRole
from app.repositories.kb_repository import KBRepository


def _make_user(role: str = "user", user_id=None):
    user = MagicMock()
    user.id = user_id or uuid4()
    user.role = role
    return user


async def _create_kb(db_session: AsyncSession, owner_id):
    repo = KBRepository(db_session)
    kb = await repo.create(name="RBAC 测试库", owner_id=owner_id)
    await db_session.commit()
    return kb


@pytest.mark.unit
class TestCheckKBPermission:
    """知识库权限校验"""

    @pytest.mark.asyncio
    async def test_owner_has_full_access(self, db_session: AsyncSession):
        """所有者拥有全部权限"""
        owner = _make_user()
        kb = await _create_kb(db_session, owner.id)
        result = await check_kb_permission(db_session, kb.id, owner, MemberRole.ADMIN)
        assert result.id == kb.id

    @pytest.mark.asyncio
    async def test_super_admin_bypass(self, db_session: AsyncSession):
        """全局 super_admin 可访问任意知识库"""
        kb = await _create_kb(db_session, uuid4())
        admin = _make_user(role=UserRole.SUPER_ADMIN)
        result = await check_kb_permission(db_session, kb.id, admin, MemberRole.ADMIN)
        assert result.id == kb.id

    @pytest.mark.asyncio
    async def test_admin_bypass(self, db_session: AsyncSession):
        """全局 admin 可访问任意知识库"""
        kb = await _create_kb(db_session, uuid4())
        admin = _make_user(role=UserRole.ADMIN)
        result = await check_kb_permission(db_session, kb.id, admin, MemberRole.ADMIN)
        assert result.id == kb.id

    @pytest.mark.asyncio
    async def test_member_role_rank(self, db_session: AsyncSession):
        """成员按角色等级校验：editor 可上传不可删，viewer 只读"""
        kb = await _create_kb(db_session, uuid4())
        repo = KBRepository(db_session)
        editor = _make_user()
        viewer = _make_user()
        await repo.add_member(kb.id, editor.id, MemberRole.EDITOR)
        await repo.add_member(kb.id, viewer.id, MemberRole.VIEWER)
        await db_session.commit()

        # editor 满足 EDITOR 要求，不满足 ADMIN 要求
        await check_kb_permission(db_session, kb.id, editor, MemberRole.EDITOR)
        with pytest.raises(ForbiddenException):
            await check_kb_permission(db_session, kb.id, editor, MemberRole.ADMIN)

        # viewer 满足 VIEWER 要求，不满足 EDITOR 要求
        await check_kb_permission(db_session, kb.id, viewer, MemberRole.VIEWER)
        with pytest.raises(ForbiddenException):
            await check_kb_permission(db_session, kb.id, viewer, MemberRole.EDITOR)

    @pytest.mark.asyncio
    async def test_kb_admin_member_full_access(self, db_session: AsyncSession):
        """知识库 admin 成员拥有库内全部权限"""
        kb = await _create_kb(db_session, uuid4())
        repo = KBRepository(db_session)
        member = _make_user()
        await repo.add_member(kb.id, member.id, MemberRole.ADMIN)
        await db_session.commit()
        await check_kb_permission(db_session, kb.id, member, MemberRole.ADMIN)

    @pytest.mark.asyncio
    async def test_non_member_forbidden(self, db_session: AsyncSession):
        """非成员无权访问"""
        kb = await _create_kb(db_session, uuid4())
        stranger = _make_user()
        with pytest.raises(ForbiddenException):
            await check_kb_permission(db_session, kb.id, stranger, MemberRole.VIEWER)

    @pytest.mark.asyncio
    async def test_kb_not_found(self, db_session: AsyncSession):
        """知识库不存在抛 NotFound"""
        with pytest.raises(NotFoundException):
            await check_kb_permission(db_session, uuid4(), _make_user(), MemberRole.VIEWER)


@pytest.mark.unit
class TestRequireRole:
    """全局角色依赖"""

    @pytest.mark.asyncio
    async def test_allowed_role(self):
        dep = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)
        admin = _make_user(role=UserRole.ADMIN)
        assert await dep(current_user=admin) is admin

    @pytest.mark.asyncio
    async def test_denied_role(self):
        dep = require_role(UserRole.ADMIN)
        with pytest.raises(ForbiddenException):
            await dep(current_user=_make_user(role=UserRole.USER))
