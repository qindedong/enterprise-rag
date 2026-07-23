"""
对话和消息 ORM 模型
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base, TimestampMixin, UUIDMixin


class ConvStatus(enum.StrEnum):
    """对话状态"""

    ACTIVE = "active"
    ARCHIVED = "archived"


class MsgRole(enum.StrEnum):
    """消息角色"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MsgFeedback(enum.StrEnum):
    """消息反馈"""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class Conversation(Base, UUIDMixin, TimestampMixin):
    """对话会话表"""

    __tablename__ = "conversations"

    kb_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(500), default=None)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[ConvStatus] = mapped_column(
        SAEnum(ConvStatus, name="conv_status", create_type=False),
        default=ConvStatus.ACTIVE,
    )

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation {self.id} by {self.user_id}>"


class Message(Base, UUIDMixin):
    """消息表"""

    __tablename__ = "messages"

    conversation_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MsgRole] = mapped_column(
        SAEnum(MsgRole, name="msg_role", create_type=False), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[dict] = mapped_column(JSON, default=list)
    retrieval_docs: Mapped[dict] = mapped_column(JSON, default=list)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[MsgFeedback | None] = mapped_column(
        SAEnum(MsgFeedback, name="msg_feedback", create_type=False), default=None, nullable=True
    )
    feedback_comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )

    # 关系
    conversation = relationship("Conversation", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message role={self.role} in conv={self.conversation_id}>"
