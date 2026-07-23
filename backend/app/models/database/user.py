"""
用户 ORM 模型
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base, TimestampMixin, UUIDMixin


class UserRole(enum.StrEnum):
    """用户角色"""

    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    USER = "user"


class User(Base, UUIDMixin, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    # 登录信息
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    # 个人信息
    display_name: Mapped[str | None] = mapped_column(String(100), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)

    # 角色与状态
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", create_type=False),
        default=UserRole.USER,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 时间
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    # 关系
    knowledge_bases = relationship("KnowledgeBase", back_populates="owner")
    kb_memberships = relationship("KBMember", back_populates="user")
    conversations = relationship("Conversation", back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.username}>"
