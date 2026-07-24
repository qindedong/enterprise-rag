"""
API Key 数据访问层
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.api_key import APIKey


class APIKeyRepository:
    """API Key 数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: UUID,
        name: str,
        prefix: str,
        key_hash: str,
        expires_at: datetime | None = None,
    ) -> APIKey:
        """创建 API Key 记录"""
        key = APIKey(
            user_id=user_id,
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            expires_at=expires_at,
        )
        self.session.add(key)
        await self.session.flush()
        return key

    async def find_by_hash(self, key_hash: str) -> APIKey | None:
        """按哈希查找（认证用）"""
        result = await self.session.execute(
            select(APIKey).where(APIKey.key_hash == key_hash, APIKey.is_active.is_(True))
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[APIKey]:
        """列出用户的所有 Key（含已吊销，便于审计）"""
        result = await self.session.execute(
            select(APIKey).where(APIKey.user_id == user_id).order_by(APIKey.created_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_id(self, key_id: UUID) -> APIKey | None:
        """按 ID 查找"""
        result = await self.session.execute(select(APIKey).where(APIKey.id == key_id))
        return result.scalar_one_or_none()

    async def revoke(self, key_id: UUID) -> None:
        """吊销 Key（软删除）"""
        await self.session.execute(
            update(APIKey).where(APIKey.id == key_id).values(is_active=False)
        )

    async def touch_last_used(self, key_id: UUID) -> None:
        """更新最近使用时间（best-effort）"""
        await self.session.execute(
            update(APIKey).where(APIKey.id == key_id).values(last_used_at=datetime.now(UTC))
        )
