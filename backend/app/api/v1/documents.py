"""
文档管理 API 接口

路由：
    POST   /api/v1/knowledge-bases/{kb_id}/documents      — 上传文档
    GET    /api/v1/knowledge-bases/{kb_id}/documents      — 文档列表
    GET    /api/v1/documents/{doc_id}                       — 文档详情
    DELETE /api/v1/documents/{doc_id}                       — 删除文档
    POST   /api/v1/documents/{doc_id}/reprocess             — 重新处理
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import JSONResponse

from app.api.deps import get_current_user, get_db, get_kb_repository
from app.core.logger import get_logger
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.qdrant_client import QdrantStore
from app.models.request_response.response import APIResponse, PageInfo, PaginatedData, PaginatedResponse
from app.repositories.document_repository import ChunkRepository, DocumentRepository
from app.repositories.kb_repository import KBRepository
from app.services.document_service import DocumentService
from app.core.exceptions import ValidationException

logger = get_logger(__name__)

router = APIRouter(tags=["文档管理"])

# AI 服务（延迟初始化，仅在 API Key 存在时创建）
_embedding_client = None
_qdrant_store = None


def _get_embedding_client():
    """延迟初始化 Embedding 客户端"""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


def _get_qdrant_store():
    """延迟初始化 Qdrant 客户端"""
    global _qdrant_store
    if _qdrant_store is None:
        _qdrant_store = QdrantStore()
    return _qdrant_store


def get_document_service(db=Depends(get_db)):
    """文档 Service 注入"""
    return DocumentService(
        doc_repo=DocumentRepository(db),
        chunk_repo=ChunkRepository(db),
        embedding_client=_get_embedding_client(),
        qdrant_store=_get_qdrant_store(),
    )


@router.post("/knowledge-bases/{kb_id}/documents", summary="上传文档", status_code=202)
async def upload_document(
    kb_id: str,
    file: UploadFile = File(...),
    service: DocumentService = Depends(get_document_service),
):
    """上传文档到知识库，自动触发解析、分块、向量化"""
    # 校验知识库存在
    kb_repo = KBRepository(service.doc_repo.session)
    kb = await kb_repo.find_by_id(UUID(kb_id))
    if not kb:
        from app.core.exceptions import NotFoundException
        raise NotFoundException("知识库", kb_id)

    content = await file.read()
    mime_type = file.content_type or "application/octet-stream"

    result = await service.upload_document(
        kb_id=UUID(kb_id),
        filename=file.filename or "unknown",
        mime_type=mime_type,
        content=content,
    )

    return APIResponse(code=202, message="文档已提交处理", data=result)


@router.get("/knowledge-bases/{kb_id}/documents", summary="获取文档列表")
async def list_documents(
    kb_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    file_type: str | None = Query(None),
    search: str | None = Query(None),
    service: DocumentService = Depends(get_document_service),
):
    """分页查询知识库下的文档列表"""
    items, total = await service.list_documents(
        kb_id=UUID(kb_id),
        page=page,
        page_size=page_size,
        status=status,
        file_type=file_type,
        search=search,
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, page_info=PageInfo(total=total, page=page, page_size=page_size))
    )


@router.get("/documents/{doc_id}", summary="获取文档详情")
async def get_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
):
    """获取文档详细信息（含分块列表）"""
    result = await service.get_detail(UUID(doc_id))
    return APIResponse(data=result)


@router.delete("/documents/{doc_id}", summary="删除文档")
async def delete_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
):
    """删除文档，同步清理 Qdrant 向量"""
    await service.delete_document(UUID(doc_id))
    return APIResponse(message="文档已删除")


@router.post("/documents/{doc_id}/reprocess", summary="重新处理文档")
async def reprocess_document(
    doc_id: str,
    service: DocumentService = Depends(get_document_service),
):
    """重新处理处理失败的文档"""
    result = await service.reprocess(UUID(doc_id))
    return APIResponse(message="文档已重新提交处理", data=result)
