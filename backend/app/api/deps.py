"""
依赖注入模块

集中管理所有 FastAPI 依赖注入，包括：
- 全局配置单例
- 数据库会话（请求级）
- 各 Service 实例

使用方式:
    from app.api.deps import get_current_user, get_document_service

    @router.get("/documents")
    async def list_documents(
        current_user: User = Depends(get_current_user),
        service: DocumentService = Depends(get_document_service),
    ):
        ...
"""

from typing import AsyncGenerator

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db

# 直接导出常用依赖，避免在各模块中重复导入
__all__ = [
    "get_settings",
    "get_db",
]

# 后续 Sprint 2 会添加:
# - get_current_user（JWT 认证中间件）
# - get_user_repository
# - get_user_service
# - get_kb_repository
# - get_kb_service
# - get_document_repository
# - get_document_service
