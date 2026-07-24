"""
依赖注入模块

集中管理所有 FastAPI 依赖注入.
"""

from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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
    "get_auth_service",
    "get_current_user",
    "get_db",
    "get_kb_repository",
    "get_kb_service",
    "get_settings",
    "get_user_repository",
]

# ===== Bearer Token 认证方案 =====
_bearer_scheme = HTTPBearer(auto_error=False)

# API Key 前缀（rag_ 开头的 Bearer Token 或 X-API-Key 头按 API Key 认证）
API_KEY_PREFIX = "rag_"


def _hash_api_key(raw_key: str) -> str:
    """API Key → SHA-256 哈希"""
    import hashlib

    return hashlib.sha256(raw_key.encode()).hexdigest()


async def _authenticate_api_key(raw_key: str, db: AsyncSession) -> User:
    """API Key 认证：哈希查找 + 有效期校验 + 更新最近使用时间"""
    from app.repositories.api_key_repository import APIKeyRepository

    repo = APIKeyRepository(db)
    key = await repo.find_by_hash(_hash_api_key(raw_key))
    if not key:
        raise UnauthorizedException("API Key 无效或已吊销")

    from datetime import UTC, datetime

    expires_at = key.expires_at
    # SQLite 返回无时区的 naive datetime，统一按 UTC 处理
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at and expires_at < datetime.now(UTC):
        raise UnauthorizedException("API Key 已过期")

    user_repo = UserRepository(db)
    user = await user_repo.find_by_id(key.user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("API Key 所属用户不存在或已被禁用")

    await repo.touch_last_used(key.id)
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    解析当前用户（认证中间件），支持两种凭据：

    1. JWT Bearer Token（前端用户）
    2. API Key（开放 API）：`Authorization: Bearer rag_xxx` 或 `X-API-Key: rag_xxx`

    在所有需要认证的接口中使用:
        current_user: User = Depends(get_current_user)
    """
    # API Key 认证（X-API-Key 头优先）
    if x_api_key:
        return await _authenticate_api_key(x_api_key, db)

    if not credentials:
        raise UnauthorizedException("请先登录")

    token = credentials.credentials

    # rag_ 前缀的 Bearer Token 按 API Key 处理
    if token.startswith(API_KEY_PREFIX):
        return await _authenticate_api_key(token, db)

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedException("无效的 Token 类型")
    except Exception:
        raise UnauthorizedException("Token 无效或已过期") from None

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
