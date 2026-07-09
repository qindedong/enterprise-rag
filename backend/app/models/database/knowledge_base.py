"""
知识库 ORM 模型
"""

from sqlalchemy import Integer, String, Text, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey

from app.models.database.base import Base, TimestampMixin, UUIDMixin

import enum


class KBStatus(str, enum.Enum):
    """知识库状态"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class KnowledgeBase(Base, UUIDMixin, TimestampMixin):
    """知识库表"""

    __tablename__ = "knowledge_bases"

    # 基本信息
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    # 所有者
    owner_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    # 处理配置
    embedding_model: Mapped[str] = mapped_column(String(100), default="text-embedding-3-large")
    chunk_size: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # 状态
    status: Mapped[KBStatus] = mapped_column(
        SAEnum(KBStatus, name="kb_status", create_type=False),
        default=KBStatus.ACTIVE,
        nullable=False,
    )

    # 扩展元数据
    metadata_: Mapped[dict] = mapped_column(JSON, default=dict, name="metadata")

    # 关系
    owner = relationship("User", back_populates="knowledge_bases")
    members = relationship("KBMember", back_populates="knowledge_base", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")
    chunks = relationship("DocumentChunk", back_populates="knowledge_base", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="knowledge_base")

    def __repr__(self) -> str:
        return f"<KnowledgeBase {self.name}>"


class MemberRole(str, enum.Enum):
    """知识库成员角色"""
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class KBMember(Base, UUIDMixin):
    """知识库成员关联表"""

    __tablename__ = "kb_members"

    kb_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MemberRole] = mapped_column(
        SAEnum(MemberRole, name="member_role", create_type=False),
        default=MemberRole.VIEWER,
        nullable=False,
    )

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="members")
    user = relationship("User", back_populates="kb_memberships")

    def __repr__(self) -> str:
        return f"<KBMember kb={self.kb_id} user={self.user_id} role={self.role}>"
