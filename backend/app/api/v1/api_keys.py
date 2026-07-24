"""
API Key 管理 API 接口

路由：
    POST   /api/v1/api-keys           — 创建 Key（明文仅返回一次）
    GET    /api/v1/api-keys           — 我的 Key 列表（脱敏）
    DELETE /api/v1/api-keys/{key_id}  — 吊销 Key
"""

import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import _hash_api_key, get_current_user, get_db
from app.core.exceptions import ForbiddenException, NotFoundException
from app.core.logger import get_logger
from app.models.database.user import User
from app.models.request_response.response import APIResponse
from app.repositories.api_key_repository import APIKeyRepository

logger = get_logger(__name__)

router = APIRouter(prefix="/api-keys", tags=["API Key 管理"])


class CreateAPIKeyRequest(BaseModel):
    """创建 API Key 请求"""

    name: str = Field(..., min_length=1, max_length=100, description="用途备注")
    expires_days: int | None = Field(None, ge=1, le=365, description="有效期（天），不填永久有效")


def _to_response(key, include_secret: str | None = None) -> dict:
    data = {
        "id": str(key.id),
        "name": key.name,
        "prefix": key.prefix,
        "masked_key": f"{key.prefix}{'•' * 8}",
        "is_active": key.is_active,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "created_at": key.created_at.isoformat() if key.created_at else None,
    }
    if include_secret:
        data["api_key"] = include_secret
    return data


@router.post("", summary="创建 API Key", status_code=201)
async def create_api_key(
    req: CreateAPIKeyRequest,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """创建 API Key。**完整 Key 仅此一次返回，请妥善保存。**"""
    raw_key = f"rag_{secrets.token_urlsafe(32)}"
    prefix = raw_key[:12]  # rag_ + 8 位，用于列表辨认

    expires_at = datetime.now(UTC) + timedelta(days=req.expires_days) if req.expires_days else None

    repo = APIKeyRepository(db)
    key = await repo.create(
        user_id=current_user.id,
        name=req.name,
        prefix=prefix,
        key_hash=_hash_api_key(raw_key),
        expires_at=expires_at,
    )
    await db.commit()

    logger.info(f"API Key 已创建: user={current_user.id}, prefix={prefix}")
    return APIResponse(
        code=201, message="API Key 已创建，请立即保存", data=_to_response(key, raw_key)
    )


@router.get("", summary="我的 API Key 列表")
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """列出当前用户的所有 API Key（脱敏显示）"""
    repo = APIKeyRepository(db)
    keys = await repo.list_by_user(current_user.id)
    return APIResponse(data=[_to_response(k) for k in keys])


@router.delete("/{key_id}", summary="吊销 API Key")
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """吊销 API Key（仅可操作自己的 Key）"""
    repo = APIKeyRepository(db)
    key = await repo.find_by_id(UUID(key_id))
    if not key:
        raise NotFoundException("API Key", key_id)
    if key.user_id != current_user.id:
        raise ForbiddenException("只能吊销自己的 API Key")

    await repo.revoke(UUID(key_id))
    await db.commit()
    logger.info(f"API Key 已吊销: {key.prefix} by user={current_user.id}")
    return APIResponse(message="API Key 已吊销")
