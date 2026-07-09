"""
RAG 问答 API 接口

路由：
    POST /api/v1/knowledge-bases/{kb_id}/chat      — RAG 问答（SSE 流式）
    POST /api/v1/knowledge-bases/{kb_id}/chat/sync  — RAG 问答（非流式）
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.core.exceptions import NotFoundException, ValidationException
from app.core.logger import get_logger
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.llm_client import LLMClient
from app.infrastructure.qdrant_client import QdrantStore
from app.models.request_response.response import APIResponse
from app.rag.pipeline import RetrievalPipeline
from app.rag.query_rewriter import QueryRewriter
from app.rag.reranker import Reranker
from app.repositories.kb_repository import KBRepository
from app.services.rag_service import RAGService

logger = get_logger(__name__)

router = APIRouter(tags=["RAG 问答"])

# AI 服务（延迟初始化）
_embedding_client = None
_llm_client = None
_qdrant_store = None
_rag_service = None


def _get_rag_service(db):
    """获取 RAG 服务单例"""
    global _embedding_client, _llm_client, _qdrant_store, _rag_service

    if _rag_service is None:
        _embedding_client = EmbeddingClient()
        _llm_client = LLMClient()
        _qdrant_store = QdrantStore()

        query_rewriter = QueryRewriter(_llm_client)
        reranker = Reranker()
        retrieval_pipeline = RetrievalPipeline(_embedding_client, _qdrant_store, query_rewriter, reranker)
        _rag_service = RAGService(retrieval_pipeline, _llm_client)

    return _rag_service


class ChatRequest(BaseModel):
    """RAG 问答请求"""
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    conversation_id: str | None = Field(None, description="对话 ID（多轮对话）")
    top_k: int = Field(50, ge=1, le=100, description="检索候选数")
    temperature: float = Field(0.3, ge=0, le=1, description="LLM 温度")


@router.post("/knowledge-bases/{kb_id}/chat", summary="RAG 问答（流式）")
async def rag_chat_stream(
    kb_id: str,
    req: ChatRequest,
    db=Depends(get_db),
):
    """
    RAG 问答 — SSE 流式输出

    事件类型：
        token    — 生成的文本片段
        citation — 引用来源列表
        done     — 完成 + 统计信息
        error    — 错误信息
    """
    # 校验知识库
    kb_repo = KBRepository(db)
    kb = await kb_repo.find_by_id(UUID(kb_id))
    if not kb:
        raise NotFoundException("知识库", kb_id)

    service = _get_rag_service(db)

    async def event_stream():
        async for event in service.ask_stream(req.question, UUID(kb_id)):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/knowledge-bases/{kb_id}/chat/sync", summary="RAG 问答（非流式）")
async def rag_chat_sync(
    kb_id: str,
    req: ChatRequest,
    db=Depends(get_db),
) -> APIResponse[dict]:
    """RAG 问答 — 非流式，返回完整 JSON 响应"""
    kb_repo = KBRepository(db)
    kb = await kb_repo.find_by_id(UUID(kb_id))
    if not kb:
        raise NotFoundException("知识库", kb_id)

    service = _get_rag_service(db)
    result = await service.ask(req.question, UUID(kb_id))
    return APIResponse(data=result)
