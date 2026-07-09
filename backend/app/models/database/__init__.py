"""
数据库 ORM 模型包

导入所有模型以确保 Alembic autogenerate 能检测到.
"""

from app.models.database.base import Base, TimestampMixin, UUIDMixin
from app.models.database.user import User
from app.models.database.knowledge_base import KnowledgeBase, KBMember
from app.models.database.document import Document, DocumentChunk

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "KnowledgeBase",
    "KBMember",
    "Document",
    "DocumentChunk",
]
