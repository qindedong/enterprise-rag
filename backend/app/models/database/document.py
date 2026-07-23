"""
文档 ORM 模型
"""

import enum

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.database.base import Base, TimestampMixin, UUIDMixin


class DocType(enum.StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    MD = "md"
    TXT = "txt"
    HTML = "html"
    IMAGE = "image"


class DocStatus(enum.StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DELETED = "deleted"


class Document(Base, UUIDMixin, TimestampMixin):
    """文档表"""

    __tablename__ = "documents"

    kb_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[DocType] = mapped_column(
        SAEnum(DocType, name="doc_type", create_type=False), nullable=False
    )
    file_size: Mapped[int | None] = mapped_column(BigInteger, default=None)
    file_path: Mapped[str | None] = mapped_column(String(1000), default=None)
    content_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    status: Mapped[DocStatus] = mapped_column(
        SAEnum(DocStatus, name="doc_status", create_type=False),
        default=DocStatus.PENDING,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_: Mapped[dict] = mapped_column(JSON, default=dict, name="metadata")

    # 关系
    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Document {self.title}>"


class DocumentChunk(Base, UUIDMixin):
    """文档分块表"""

    __tablename__ = "document_chunks"

    document_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    kb_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # jieba 分词结果（空格连接），供 PG 生成 tsvector 做 BM25 检索
    content_segmented: Mapped[str | None] = mapped_column(Text, default=None)
    token_count: Mapped[int | None] = mapped_column(Integer, default=None)
    page_number: Mapped[int | None] = mapped_column(Integer, default=None)
    section_title: Mapped[str | None] = mapped_column(String(500), default=None)
    metadata_: Mapped[dict] = mapped_column(JSON, default=dict, name="metadata")
    created_at: Mapped[str] = mapped_column(
        String(50),
        default=lambda: (
            __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        ),
    )

    # 关系
    document = relationship("Document", back_populates="chunks")
    knowledge_base = relationship("KnowledgeBase", back_populates="chunks")

    def __repr__(self) -> str:
        return f"<DocumentChunk doc={self.document_id} #{self.chunk_index}>"
