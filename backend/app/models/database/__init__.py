"""
数据库 ORM 模型包

导入所有模型以确保 Alembic autogenerate 能检测到.
"""

from app.models.database.base import Base, TimestampMixin, UUIDMixin
from app.models.database.conversation import Conversation, Message
from app.models.database.document import Document, DocumentChunk
from app.models.database.knowledge_base import KBMember, KnowledgeBase
from app.models.database.user import User

__all__ = [
    "Base",
    "Conversation",
    "Document",
    "DocumentChunk",
    "KBMember",
    "KnowledgeBase",
    "Message",
    "TimestampMixin",
    "UUIDMixin",
    "User",
]
