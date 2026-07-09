"""
知识库数据访问层

封装所有知识库相关的数据库查询，不包含任何业务逻辑.
"""

from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.database.knowledge_base import KnowledgeBase, KBMember, KBStatus, MemberRole


class KBRepository:
    """知识库数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        name: str,
        owner_id: UUID,
        description: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model: str = "text-embedding-3-large",
    ) -> KnowledgeBase:
        """创建知识库"""
        kb = KnowledgeBase(
            name=name,
            description=description,
            owner_id=owner_id,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
        )
        self.session.add(kb)
        await self.session.flush()
        return kb

    async def find_by_id(self, kb_id: UUID) -> KnowledgeBase | None:
        """按 ID 查找知识库（包含 owner）"""
        result = await self.session.execute(
            select(KnowledgeBase)
            .options(joinedload(KnowledgeBase.owner))
            .where(KnowledgeBase.id == kb_id, KnowledgeBase.status != KBStatus.DELETED)
        )
        return result.unique().scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, page: int = 1, page_size: int = 20, search: str | None = None
    ) -> tuple[list[KnowledgeBase], int]:
        """分页查询用户有权限的知识库"""
        # 子查询：用户创建的知识库
        owned = select(KnowledgeBase.id).where(
            KnowledgeBase.owner_id == user_id,
            KnowledgeBase.status != KBStatus.DELETED,
        )
        # 子查询：用户是成员的知识库
        member_of = select(KBMember.kb_id).where(KBMember.user_id == user_id)
        # 合并
        kb_ids = owned.union(member_of).subquery()

        conditions = [
            KnowledgeBase.id.in_(select(kb_ids.c.id)),
            KnowledgeBase.status != KBStatus.DELETED,
        ]

        if search:
            conditions.append(KnowledgeBase.name.ilike(f"%{search}%"))

        # 统计总数
        count_query = select(func.count()).where(and_(*conditions))
        total = (await self.session.execute(count_query)).scalar() or 0

        # 分页查询
        query = (
            select(KnowledgeBase)
            .options(joinedload(KnowledgeBase.owner))
            .where(and_(*conditions))
            .order_by(KnowledgeBase.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(query)
        knowledge_bases = result.unique().scalars().all()

        return list(knowledge_bases), total

    async def update(self, kb_id: UUID, **kwargs) -> None:
        """更新知识库字段"""
        from sqlalchemy import update as sql_update
        from datetime import datetime, timezone

        kwargs["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            sql_update(KnowledgeBase).where(KnowledgeBase.id == kb_id).values(**kwargs)
        )

    async def soft_delete(self, kb_id: UUID) -> None:
        """软删除知识库"""
        from sqlalchemy import update as sql_update
        from datetime import datetime, timezone

        await self.session.execute(
            sql_update(KnowledgeBase)
            .where(KnowledgeBase.id == kb_id)
            .values(status=KBStatus.DELETED, updated_at=datetime.now(timezone.utc))
        )

    async def find_by_name_and_owner(self, name: str, owner_id: UUID) -> KnowledgeBase | None:
        """检查知识库名称是否重复（同一用户下）"""
        result = await self.session.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.name == name,
                KnowledgeBase.owner_id == owner_id,
                KnowledgeBase.status != KBStatus.DELETED,
            )
        )
        return result.scalar_one_or_none()

    async def count_by_owner(self, owner_id: UUID) -> int:
        """统计用户拥有的知识库数量"""
        result = await self.session.execute(
            select(func.count()).where(
                KnowledgeBase.owner_id == owner_id,
                KnowledgeBase.status != KBStatus.DELETED,
            )
        )
        return result.scalar() or 0

    # ===== 成员管理 =====

    async def add_member(self, kb_id: UUID, user_id: UUID, role: MemberRole = MemberRole.VIEWER) -> KBMember:
        """添加知识库成员"""
        member = KBMember(kb_id=kb_id, user_id=user_id, role=role)
        self.session.add(member)
        await self.session.flush()
        return member

    async def remove_member(self, kb_id: UUID, user_id: UUID) -> None:
        """移除知识库成员"""
        from sqlalchemy import delete

        await self.session.execute(
            delete(KBMember).where(KBMember.kb_id == kb_id, KBMember.user_id == user_id)
        )

    async def get_member(self, kb_id: UUID, user_id: UUID) -> KBMember | None:
        """获取成员信息"""
        result = await self.session.execute(
            select(KBMember).where(KBMember.kb_id == kb_id, KBMember.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_members(self, kb_id: UUID) -> list[KBMember]:
        """获取知识库所有成员"""
        result = await self.session.execute(
            select(KBMember)
            .options(joinedload(KBMember.user))
            .where(KBMember.kb_id == kb_id)
        )
        return list(result.unique().scalars().all())

    async def is_member(self, kb_id: UUID, user_id: UUID) -> bool:
        """判断用户是否是知识库成员（含 owner）"""
        kb = await self.find_by_id(kb_id)
        if kb and kb.owner_id == user_id:
            return True
        member = await self.get_member(kb_id, user_id)
        return member is not None
