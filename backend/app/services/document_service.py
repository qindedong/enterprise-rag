"""
文档管理服务

负责文档上传、解析、分块、向量化的完整流程编排.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from qdrant_client.models import PointStruct

from app.core.config import get_settings
from app.core.exceptions import NotFoundException, ValidationException, DuplicateException, ProcessingException
from app.core.logger import get_logger
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.qdrant_client import QdrantStore
from app.models.database.document import DocStatus, DocType
from app.parsers.registry import ParserRegistry
from app.repositories.document_repository import ChunkRepository, DocumentRepository
from app.utils.text_splitter import TextSplitter

logger = get_logger(__name__)

settings = get_settings()

# 允许的文件类型
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "text/markdown": "md",
    "text/x-markdown": "md",
    "text/plain": "txt",
    "application/octet-stream": "txt",  # curl 上传 .txt 时可能识别为 octet-stream
}


class DocumentService:
    """文档管理服务"""

    def __init__(
        self,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        embedding_client: EmbeddingClient,
        qdrant_store: QdrantStore,
    ):
        self.doc_repo = doc_repo
        self.chunk_repo = chunk_repo
        self.embedding_client = embedding_client
        self.qdrant_store = qdrant_store

    async def upload_document(
        self,
        kb_id: UUID,
        filename: str,
        mime_type: str,
        content: bytes,
    ) -> dict:
        """
        上传文档（异步模式）

        流程：校验 → 去重 → 保存文件 → 创建记录 → 推入 Redis 队列

        Worker 会在后台异步完成解析→分块→向量化→Qdrant 的完整流程。
        前端可通过 GET /documents/{doc_id} 轮询处理状态。

        Args:
            kb_id: 知识库 ID
            filename: 原始文件名
            mime_type: 文件 MIME 类型
            content: 文件字节内容

        Returns:
            文档信息字典（初始状态为 pending）

        Raises:
            ValidationException: 文件类型不支持或大小超限
            DuplicateException: 相同内容的文档已存在
        """
        # 1. 文件校验
        if mime_type not in ALLOWED_MIME_TYPES:
            # 尝试根据文件扩展名推断
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            EXT_TO_MIME = {"pdf": "application/pdf", "md": "text/markdown", "txt": "text/plain", "markdown": "text/markdown"}
            mime_type = EXT_TO_MIME.get(ext, mime_type)

        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValidationException(
                f"不支持的文件类型: {mime_type}。支持: PDF, Markdown, TXT"
            )

        file_size = len(content)
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise ValidationException(f"文件过大 ({file_size / 1024 / 1024:.1f}MB)，最大 {settings.MAX_FILE_SIZE_MB}MB")

        # 2. 计算内容哈希（去重）
        content_hash = hashlib.sha256(content).hexdigest()
        existing = await self.doc_repo.find_by_hash(kb_id, content_hash)
        if existing:
            raise DuplicateException("文档", f"相同内容的文档已存在: {existing.title}")

        # 3. 保存文件
        file_path = self._save_file(kb_id, filename, content)
        file_ext = ALLOWED_MIME_TYPES[mime_type]

        # 4. 创建文档记录
        doc = await self.doc_repo.create(
            kb_id=kb_id,
            title=filename,
            file_type=file_ext,
            file_size=file_size,
            file_path=file_path,
            content_hash=content_hash,
        )

        logger.info(f"文档记录已创建: {doc.id} ({filename}), 状态: pending")

        # 5. 推入 Redis 队列（异步 Worker 处理）
        try:
            await self._enqueue_for_processing(doc.id, kb_id, file_path, file_ext)
            logger.info(f"文档已推入处理队列: {doc.id}")
        except Exception as e:
            logger.error(f"推入队列失败: {doc.id}, 原因: {e}", exc_info=True)
            await self.doc_repo.update_status(doc.id, DocStatus.FAILED, error_message=f"推入队列失败: {e}")
            raise ProcessingException(f"文档处理失败: {e}")

        # 6. 返回文档信息（状态为 pending）
        return self._to_response(doc)

    async def _enqueue_for_processing(self, doc_id: UUID, kb_id: UUID, file_path: str, file_ext: str) -> None:
        """将文档处理任务推入 Redis 队列"""
        import redis.asyncio as aioredis

        try:
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            task = json.dumps({
                "doc_id": str(doc_id),
                "kb_id": str(kb_id),
                "file_path": file_path,
                "file_type": file_ext,
            })
            await r.lpush("rag:doc_process_queue", task)
            await r.aclose()
        except Exception:
            # Redis 不可用时降级为同步处理
            logger.warning("Redis 不可用，降级为同步处理模式")
            await self._process_document(doc_id, kb_id, file_path, file_ext)

    async def _process_document(self, doc_id: UUID, kb_id: UUID, file_path: str, file_ext: str) -> None:
        """处理文档：解析 → 分块 → 向量化 → 写入 Qdrant"""
        await self.doc_repo.update_status(doc_id, DocStatus.PROCESSING)

        # Step 1: 解析
        logger.info(f"开始解析文档: {doc_id}")
        try:
            parser = ParserRegistry.get_parser(f"application/{file_ext}" if file_ext == "pdf" else f"text/{file_ext}")
            raw_text = parser.parse(file_path)
        except Exception as e:
            # 尝试通用解析
            from app.parsers.text_parser import TextParser
            raw_text = TextParser().parse(file_path)

        if not raw_text or not raw_text.strip():
            raise ProcessingException("未能提取到有效的文字内容")

        # Step 2: 分块
        from app.repositories.kb_repository import KBRepository
        # 这里简化：使用默认分块参数
        splitter = TextSplitter(chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP)
        result = splitter.split(raw_text)
        if result.total_chunks == 0:
            raise ProcessingException("分块结果为空")

        # Step 3: 插入 Chunk 记录
        chunks = await self.chunk_repo.bulk_insert(doc_id, kb_id, result.chunks, result.token_counts)

        # Step 4: 向量化
        embeddings = await self.embedding_client.embed_batch(result.chunks)

        # Step 5: 写入 Qdrant
        points = []
        for chunk, embedding in zip(chunks, embeddings):
            point = PointStruct(
                id=str(chunk.id),
                vector=embedding,
                payload={
                    "kb_id": str(kb_id),
                    "document_id": str(doc_id),
                    "chunk_id": str(chunk.id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content[:1000],  # 只存储前 1000 字符供预览
                    "page_number": chunk.page_number,
                    "section_title": chunk.section_title,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            points.append(point)

        self.qdrant_store.upsert(points)

        # Step 6: 更新状态
        await self.doc_repo.update_status(doc_id, DocStatus.COMPLETED, chunk_count=result.total_chunks)
        logger.info(f"文档处理完成: {doc_id}, 分块数: {result.total_chunks}")

    def _save_file(self, kb_id: UUID, filename: str, content: bytes) -> str:
        """保存文件到磁盘"""
        upload_dir = Path(settings.UPLOAD_DIR) / str(kb_id)
        os.makedirs(upload_dir, exist_ok=True)

        # 防止文件名冲突
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        safe_name = f"{timestamp}_{filename}"
        file_path = upload_dir / safe_name

        with open(file_path, "wb") as f:
            f.write(content)

        return str(file_path)

    async def list_documents(
        self,
        kb_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
        file_type: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict], int]:
        """获取文档列表"""
        docs, total = await self.doc_repo.list_by_kb(
            kb_id=kb_id,
            page=page,
            page_size=page_size,
            status=status,
            file_type=file_type,
            search=search,
        )
        return [self._to_response(d) for d in docs], total

    async def get_detail(self, doc_id: UUID) -> dict:
        """获取文档详情（含分块列表）"""
        doc = await self.doc_repo.find_by_id(doc_id)
        if not doc or doc.status == DocStatus.DELETED:
            raise NotFoundException("文档", str(doc_id))

        chunks = await self.chunk_repo.get_by_document(doc_id)
        return {
            **self._to_response(doc),
            "chunks": [
                {
                    "chunk_index": c.chunk_index,
                    "content_preview": c.content[:200] if c.content else "",
                    "token_count": c.token_count,
                    "page_number": c.page_number,
                    "section_title": c.section_title,
                }
                for c in chunks
            ],
            "metadata": doc.metadata_,
        }

    async def delete_document(self, doc_id: UUID) -> None:
        """删除文档（软删除 + 清理 Qdrant 向量）"""
        doc = await self.doc_repo.find_by_id(doc_id)
        if not doc or doc.status == DocStatus.DELETED:
            raise NotFoundException("文档", str(doc_id))

        # 1. 清理 Qdrant 向量
        self.qdrant_store.delete_by_document(str(doc_id))

        # 2. 软删除 PG 记录
        await self.doc_repo.soft_delete(doc_id)
        logger.info(f"文档已删除: {doc_id}")

    async def reprocess(self, doc_id: UUID) -> dict:
        """重新处理失败的文档"""
        doc = await self.doc_repo.find_by_id(doc_id)
        if not doc:
            raise NotFoundException("文档", str(doc_id))

        if doc.status != DocStatus.FAILED:
            raise ValidationException("只能重新处理失败的文档")

        await self._process_document(doc.id, doc.kb_id, doc.file_path, doc.file_type.value)
        updated = await self.doc_repo.find_by_id(doc_id)
        return self._to_response(updated)

    def _to_response(self, doc) -> dict:
        """将 Document 对象转为 API 响应字典"""
        # 兼容文件类型可能是 Enum 或者 str
        ft = getattr(doc, 'file_type', None)
        if ft is not None and hasattr(ft, 'value'):
            ft = ft.value
        st = getattr(doc, 'status', None)
        if st is not None and hasattr(st, 'value'):
            st = st.value
        return {
            "id": str(doc.id),
            "kb_id": str(doc.kb_id),
            "title": doc.title,
            "file_type": ft,
            "file_size": doc.file_size,
            "status": st,
            "chunk_count": doc.chunk_count or 0,
            "error_message": doc.error_message,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }
