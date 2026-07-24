"""
API Key ORM 模型

开放 API 认证凭据：第三方系统可通过 `Authorization: Bearer rag_xxx`
或 `X-API-Key: rag_xxx` 访问 API，权限等同于所属用户。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base, TimestampMixin, UUIDMixin


class APIKey(Base, UUIDMixin, TimestampMixin):
    """API Key 表（只存哈希，不存明文）"""

    __tablename__ = "api_keys"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 展示用前缀（如 rag_a1b2c3d4），用于列表中辨认
    prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    # SHA-256 哈希（明文仅在创建时返回一次）
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # 关系
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<APIKey {self.prefix}... user={self.user_id}>"
