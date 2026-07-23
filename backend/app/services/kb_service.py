"""
知识库管理服务

负责知识库 CRUD、成员管理的业务逻辑编排.
"""

from uuid import UUID

from app.core.exceptions import (
    DuplicateException,
    ForbiddenException,
    NotFoundException,
    ValidationException,
)
from app.core.logger import get_logger
from app.models.database.knowledge_base import MemberRole
from app.repositories.kb_repository import KBRepository

logger = get_logger(__name__)


class KBService:
    """知识库管理服务"""

    def __init__(self, kb_repo: KBRepository):
        self.kb_repo = kb_repo

    async def create(
        self,
        name: str,
        owner_id: UUID,
        description: str = "",
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model: str = "text-embedding-3-large",
    ) -> dict:
        """
        创建知识库

        Raises:
            ValidationException: 参数不合法
            DuplicateException: 知识库名称重复
        """
        # 校验名称
        if not name or len(name) > 255:
            raise ValidationException("知识库名称长度必须为 1-255 个字符")

        # 校验分块参数
        if chunk_size < 500 or chunk_size > 800:
            raise ValidationException("分块大小必须在 500-800 之间")
        if chunk_overlap < 50 or chunk_overlap > 200:
            raise ValidationException("重叠大小必须在 50-200 之间")

        # 检查重复
        existing = await self.kb_repo.find_by_name_and_owner(name, owner_id)
        if existing:
            raise DuplicateException("知识库", f"名称 '{name}' 已存在")

        kb = await self.kb_repo.create(
            name=name,
            owner_id=owner_id,
            description=description,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
        )

        logger.info(f"知识库创建成功: {kb.name} ({kb.id})")
        return self._to_response(kb)

    async def list_by_user(
        self, user_id: UUID, page: int = 1, page_size: int = 20, search: str | None = None
    ) -> tuple[list[dict], int]:
        """获取用户有权限的知识库列表"""
        kbs, total = await self.kb_repo.list_by_user(user_id, page, page_size, search)
        return [self._to_response(kb) for kb in kbs], total

    async def get_detail(self, kb_id: UUID, user_id: UUID) -> dict:
        """获取知识库详情（需权限校验）"""
        kb = await self.kb_repo.find_by_id_with_owner(kb_id)
        if not kb:
            raise NotFoundException("知识库", str(kb_id))

        # 权限校验
        if not await self._can_access(kb_id, user_id):
            raise ForbiddenException("您没有该知识库的访问权限")

        # 获取统计信息
        doc_count = await self.kb_repo.get_document_count(kb_id)
        chunk_count = await self.kb_repo.get_chunk_count(kb_id)
        member_count = await self.kb_repo.count_members(kb_id)

        return {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description,
            "owner": {
                "id": str(kb.owner.id) if kb.owner else None,
                "display_name": kb.owner.display_name if kb.owner else None,
            },
            "chunk_size": kb.chunk_size,
            "chunk_overlap": kb.chunk_overlap,
            "embedding_model": kb.embedding_model,
            "status": kb.status.value if kb.status else "active",
            "stats": {
                "document_count": doc_count,
                "chunk_count": chunk_count,
                "total_questions": 0,
            },
            "member_count": member_count,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        }

    async def update(self, kb_id: UUID, user_id: UUID, **kwargs) -> dict:
        """更新知识库（仅 owner 可更新）"""
        kb = await self.kb_repo.find_by_id(kb_id)
        if not kb:
            raise NotFoundException("知识库", str(kb_id))

        if kb.owner_id != user_id:
            raise ForbiddenException("只有知识库所有者可以修改配置")

        # 只更新允许的字段
        allowed_fields = {"name", "description", "chunk_size", "chunk_overlap", "embedding_model"}
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields and v is not None}

        if update_data:
            await self.kb_repo.update(kb_id, **update_data)
            logger.info(f"知识库更新成功: {kb_id}, 字段: {list(update_data.keys())}")

        updated_kb = await self.kb_repo.find_by_id(kb_id)
        return self._to_response(updated_kb)

    async def delete(self, kb_id: UUID, user_id: UUID) -> None:
        """删除知识库（仅 owner 可删除）"""
        kb = await self.kb_repo.find_by_id(kb_id)
        if not kb:
            raise NotFoundException("知识库", str(kb_id))

        if kb.owner_id != user_id:
            raise ForbiddenException("只有知识库所有者可以删除")

        await self.kb_repo.soft_delete(kb_id)
        logger.info(f"知识库已删除: {kb_id}")

    # ===== 成员管理 =====

    async def add_member(self, kb_id: UUID, owner_id: UUID, user_id: UUID, role: str) -> dict:
        """添加成员（仅 admin/owner 可操作）"""
        kb = await self.kb_repo.find_by_id(kb_id)
        if not kb:
            raise NotFoundException("知识库", str(kb_id))

        if kb.owner_id != owner_id:
            raise ForbiddenException("只有知识库所有者可以管理成员")

        member = await self.kb_repo.add_member(kb_id, user_id, MemberRole(role))
        logger.info(f"成员已添加: kb={kb_id}, user={user_id}, role={role}")
        return {
            "kb_id": str(member.kb_id),
            "user_id": str(member.user_id),
            "role": member.role.value,
        }

    async def remove_member(self, kb_id: UUID, owner_id: UUID, user_id: UUID) -> None:
        """移除成员"""
        kb = await self.kb_repo.find_by_id(kb_id)
        if not kb:
            raise NotFoundException("知识库", str(kb_id))

        if kb.owner_id != owner_id:
            raise ForbiddenException("只有知识库所有者可以管理成员")

        if user_id == owner_id:
            raise ValidationException("不能移除知识库所有者自身")

        await self.kb_repo.remove_member(kb_id, user_id)
        logger.info(f"成员已移除: kb={kb_id}, user={user_id}")

    async def list_members(self, kb_id: UUID, user_id: UUID) -> list[dict]:
        """获取成员列表"""
        if not await self._can_access(kb_id, user_id):
            raise ForbiddenException("您没有该知识库的访问权限")

        members = await self.kb_repo.list_members(kb_id)
        return [
            {
                "user_id": str(m.user_id),
                "username": m.user.username,
                "display_name": m.user.display_name,
                "role": m.role.value,
                "joined_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in members
        ]

    # ===== 内部方法 =====

    async def _can_access(self, kb_id: UUID, user_id: UUID) -> bool:
        """检查用户是否有权访问知识库"""
        return await self.kb_repo.is_member(kb_id, user_id)

    def _to_response(self, kb) -> dict:
        """转换为列表响应格式"""
        return {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description,
            "owner_id": str(kb.owner_id),
            "status": kb.status.value if kb.status else "active",
            "document_count": getattr(kb, "document_count", 0) or 0,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        }

    def _to_detail_response(self, kb) -> dict:
        """转换为详情响应格式"""
        return {
            "id": str(kb.id),
            "name": kb.name,
            "description": kb.description,
            "owner": {
                "id": str(kb.owner.id),
                "display_name": kb.owner.display_name,
            },
            "chunk_size": kb.chunk_size,
            "chunk_overlap": kb.chunk_overlap,
            "embedding_model": kb.embedding_model,
            "status": kb.status.value if kb.status else "active",
            "stats": {
                "document_count": getattr(kb, "document_count", 0) or 0,
                "chunk_count": getattr(kb, "chunk_count", 0) or 0,
                "total_questions": getattr(kb, "total_questions", 0) or 0,
            },
            "member_count": len(kb.members) if kb.members else 0,
            "created_at": kb.created_at.isoformat() if kb.created_at else None,
            "updated_at": kb.updated_at.isoformat() if kb.updated_at else None,
        }
