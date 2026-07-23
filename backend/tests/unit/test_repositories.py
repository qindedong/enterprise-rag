"""
Repository 层单元测试

测试 UserRepository / KBRepository 的核心查询逻辑.
"""

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.knowledge_base import MemberRole
from app.repositories.kb_repository import KBRepository
from app.repositories.user_repository import UserRepository


@pytest.mark.unit
class TestUserRepository:
    """UserRepository 测试"""

    @pytest.mark.asyncio
    async def test_create_user(self, db_session: AsyncSession):
        """测试：创建用户"""
        repo = UserRepository(db_session)
        user = await repo.create("testuser", "test@example.com", "hashed_pw", "测试用户")

        assert user is not None
        assert user.username == "testuser"
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_find_by_email(self, db_session: AsyncSession):
        """测试：按邮箱查找"""
        repo = UserRepository(db_session)
        await repo.create("alice", "alice@example.com", "hashed_pw")
        await db_session.commit()

        found = await repo.find_by_email("alice@example.com")
        assert found is not None
        assert found.username == "alice"

        not_found = await repo.find_by_email("nobody@example.com")
        assert not_found is None

    @pytest.mark.asyncio
    async def test_find_by_username(self, db_session: AsyncSession):
        """测试：按用户名查找"""
        repo = UserRepository(db_session)
        await repo.create("bob", "bob@example.com", "hashed_pw")
        await db_session.commit()

        found = await repo.find_by_username("bob")
        assert found is not None

        not_found = await repo.find_by_username("nobody")
        assert not_found is None


@pytest.mark.unit
class TestKBRepository:
    """KBRepository 测试"""

    @pytest.mark.asyncio
    async def test_create_kb(self, db_session: AsyncSession):
        """测试：创建知识库"""
        owner_id = uuid4()
        repo = KBRepository(db_session)

        kb = await repo.create(name="测试库", owner_id=owner_id, description="测试描述")
        assert kb.name == "测试库"
        assert kb.owner_id == owner_id

    @pytest.mark.asyncio
    async def test_find_by_name_and_owner(self, db_session: AsyncSession):
        """测试：按名称+所有者查找（去重用）"""
        owner_id = uuid4()
        repo = KBRepository(db_session)
        await repo.create(name="唯一库", owner_id=owner_id)

        found = await repo.find_by_name_and_owner("唯一库", owner_id)
        assert found is not None

        not_found = await repo.find_by_name_and_owner("不存在的库", owner_id)
        assert not_found is None

    @pytest.mark.asyncio
    async def test_add_and_list_members(self, db_session: AsyncSession):
        """测试：添加和列出成员"""
        owner_id = uuid4()
        user_id = uuid4()
        repo = KBRepository(db_session)

        kb = await repo.create(name="团队库", owner_id=owner_id)
        await repo.add_member(kb.id, user_id, MemberRole.EDITOR)

        members = await repo.list_members(kb.id)
        assert len(members) == 1
        assert members[0].user_id == user_id
        assert members[0].role == MemberRole.EDITOR

    @pytest.mark.asyncio
    async def test_remove_member(self, db_session: AsyncSession):
        """测试：移除成员"""
        owner_id = uuid4()
        user_id = uuid4()
        repo = KBRepository(db_session)

        kb = await repo.create(name="团队库", owner_id=owner_id)
        await repo.add_member(kb.id, user_id)

        await repo.remove_member(kb.id, user_id)
        members = await repo.list_members(kb.id)
        assert len(members) == 0

    @pytest.mark.asyncio
    async def test_is_member(self, db_session: AsyncSession):
        """测试：成员判断（含 owner）"""
        owner_id = uuid4()
        other_id = uuid4()
        repo = KBRepository(db_session)

        kb = await repo.create(name="所有权库", owner_id=owner_id)

        # owner 自动是成员
        assert await repo.is_member(kb.id, owner_id) is True

        # 非成员
        assert await repo.is_member(kb.id, other_id) is False
