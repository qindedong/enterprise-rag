"""
RBAC 权限控制

两层权限模型：
- 全局角色（User.role）：super_admin / admin 可访问所有知识库
- 知识库成员角色（KBMember.role）：admin > editor > viewer
  - viewer：问答、检索、查看文档、反馈统计
  - editor：viewer + 上传/重新处理文档
  - admin ：editor + 删除文档
- 知识库所有者（owner）拥有全部权限

提供 FastAPI 依赖工厂：
- require_kb_role(min_role)  — 按路径参数 kb_id 校验
- require_doc_role(min_role) — 按路径参数 doc_id 反查知识库校验
- require_role(*roles)       — 全局角色校验
"""

from uuid import UUID

from fastapi import Depends

from app.api.deps import get_current_user, get_db
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.database.knowledge_base import KnowledgeBase, MemberRole
from app.models.database.user import User, UserRole
from app.repositories.kb_repository import KBRepository

# 成员角色等级（数值越大权限越高）
_ROLE_RANK = {
    MemberRole.VIEWER: 1,
    MemberRole.EDITOR: 2,
    MemberRole.ADMIN: 3,
}


async def check_kb_permission(
    db, kb_id: UUID, user: User, min_role: MemberRole = MemberRole.VIEWER
) -> KnowledgeBase:
    """
    校验用户对知识库的操作权限

    Raises:
        NotFoundException: 知识库不存在
        ForbiddenException: 权限不足
    """
    repo = KBRepository(db)
    kb = await repo.find_by_id(kb_id)
    if not kb:
        raise NotFoundException("知识库", str(kb_id))

    # 全局管理员放行
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        return kb

    # 所有者放行
    if kb.owner_id == user.id:
        return kb

    # 成员按角色等级校验
    member = await repo.get_member(kb_id, user.id)
    if member and _ROLE_RANK[member.role] >= _ROLE_RANK[min_role]:
        return kb

    raise ForbiddenException("您没有该知识库的操作权限")


def require_kb_role(min_role: MemberRole = MemberRole.VIEWER):
    """按路径参数 kb_id 校验知识库权限的依赖工厂"""

    async def dependency(
        kb_id: str,
        current_user: User = Depends(get_current_user),
        db=Depends(get_db),
    ) -> KnowledgeBase:
        return await check_kb_permission(db, UUID(kb_id), current_user, min_role)

    return dependency


def require_doc_role(min_role: MemberRole = MemberRole.VIEWER):
    """按路径参数 doc_id 反查所属知识库并校验权限的依赖工厂"""

    async def dependency(
        doc_id: str,
        current_user: User = Depends(get_current_user),
        db=Depends(get_db),
    ):
        from app.repositories.document_repository import DocumentRepository

        doc = await DocumentRepository(db).find_by_id(UUID(doc_id))
        if not doc:
            raise NotFoundException("文档", doc_id)
        await check_kb_permission(db, doc.kb_id, current_user, min_role)
        return doc

    return dependency


def require_role(*roles: UserRole):
    """全局角色校验的依赖工厂（如系统管理接口）"""

    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise ForbiddenException("权限不足，需要管理员角色")
        return current_user

    return dependency
