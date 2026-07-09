"""
文档数据访问层
"""

from uuid import UUID

from sqlalchemy import func, select, and_, update as sql_update, delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.models.database.document import Document, DocumentChunk, DocStatus


class DocumentRepository:
    """文档数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        kb_id: UUID,
        title: str,
        file_type: str,
        file_size: int | None = None,
        file_path: str | None = None,
        content_hash: str | None = None,
    ) -> Document:
        """创建文档记录"""
        doc = Document(
            kb_id=kb_id,
            title=title,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            content_hash=content_hash,
        )
        self.session.add(doc)
        await self.session.flush()
        return doc

    async def find_by_id(self, doc_id: UUID) -> Document | None:
        """按 ID 查找文档"""
        result = await self.session.execute(select(Document).where(Document.id == doc_id))
        return result.scalar_one_or_none()

    async def find_by_hash(self, kb_id: UUID, content_hash: str) -> Document | None:
        """按内容哈希查找（去重）"""
        result = await self.session.execute(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.content_hash == content_hash,
                Document.status != DocStatus.DELETED,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(self, doc_id: UUID, status: DocStatus, **kwargs) -> None:
        """更新文档状态"""
        values = {"status": status, "updated_at": datetime.now(timezone.utc), **kwargs}
        await self.session.execute(sql_update(Document).where(Document.id == doc_id).values(**values))

    async def list_by_kb(
        self,
        kb_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        file_type: str | None = None,
        search: str | None = None,
    ) -> tuple[list[Document], int]:
        """分页查询知识库下的文档"""
        conditions = [Document.kb_id == kb_id, Document.status != DocStatus.DELETED]

        if status:
            conditions.append(Document.status == status)
        if file_type:
            conditions.append(Document.file_type == file_type)
        if search:
            conditions.append(Document.title.ilike(f"%{search}%"))

        count_query = select(func.count()).where(and_(*conditions))
        total = (await self.session.execute(count_query)).scalar() or 0

        query = (
            select(Document)
            .where(and_(*conditions))
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all()), total

    async def soft_delete(self, doc_id: UUID) -> None:
        """软删除文档"""
        await self.session.execute(
            sql_update(Document)
            .where(Document.id == doc_id)
            .values(status=DocStatus.DELETED, updated_at=datetime.now(timezone.utc))
        )


class ChunkRepository:
    """文档分块数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_insert(
        self,
        doc_id: UUID,
        kb_id: UUID,
        chunks: list[str],
        token_counts: list[int],
        metadata_list: list[dict] | None = None,
    ) -> list[DocumentChunk]:
        """批量插入分块记录"""
        records = []
        for i, content in enumerate(chunks):
            chunk = DocumentChunk(
                document_id=doc_id,
                kb_id=kb_id,
                chunk_index=i,
                content=content,
                token_count=token_counts[i] if i < len(token_counts) else None,
                section_title=metadata_list[i].get("section_title") if metadata_list and i < len(metadata_list) else None,
                page_number=metadata_list[i].get("page_number") if metadata_list and i < len(metadata_list) else None,
            )
            records.append(chunk)

        self.session.add_all(records)
        await self.session.flush()
        return records

    async def get_by_document(self, doc_id: UUID) -> list[DocumentChunk]:
        """获取文档的所有分块"""
        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id).order_by(DocumentChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def get_chunk_ids_by_document(self, doc_id: UUID) -> list[str]:
        """获取文档的所有分块 ID"""
        chunks = await self.get_by_document(doc_id)
        return [str(c.id) for c in chunks]
