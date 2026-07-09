"""
依赖注入模块

集中管理所有 FastAPI 依赖注入.
"""

from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.exceptions import UnauthorizedException
from app.core.logger import get_logger
from app.models.database.user import User
from app.repositories.kb_repository import KBRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.kb_service import KBService
from app.utils.security import decode_token

logger = get_logger(__name__)

# 直接导出常用依赖
__all__ = [
    "get_settings",
    "get_db",
    "get_current_user",
    "get_user_repository",
    "get_kb_repository",
    "get_auth_service",
    "get_kb_service",
]

# ===== Bearer Token 认证方案 =====
_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    从 JWT Token 解析当前用户（认证中间件）

    在所有需要认证的接口中使用:
        current_user: User = Depends(get_current_user)
    """
    if not credentials:
        raise UnauthorizedException("请先登录")

    token = credentials.credentials
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedException("无效的 Token 类型")
    except Exception:
        raise UnauthorizedException("Token 无效或已过期")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Token 格式无效")

    user_repo = UserRepository(db)
    user = await user_repo.find_by_id(UUID(user_id))
    if not user or not user.is_active:
        raise UnauthorizedException("用户不存在或已被禁用")

    return user


# ===== Repository 注入 =====

def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    """用户 Repository 注入"""
    return UserRepository(db)


def get_kb_repository(db: AsyncSession = Depends(get_db)) -> KBRepository:
    """知识库 Repository 注入"""
    return KBRepository(db)


# ===== Service 注入 =====

def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """认证 Service 注入"""
    return AuthService(user_repo)


def get_kb_service(
    kb_repo: KBRepository = Depends(get_kb_repository),
) -> KBService:
    """知识库 Service 注入"""
    return KBService(kb_repo)
