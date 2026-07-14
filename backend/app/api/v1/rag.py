"""
RAG 问答 API + 对话管理

路由：
    POST   /api/v1/knowledge-bases/{kb_id}/chat          — RAG 问答（SSE 流式）
    POST   /api/v1/knowledge-bases/{kb_id}/chat/sync     — RAG 问答（非流式）
    POST   /api/v1/knowledge-bases/{kb_id}/conversations — 创建对话
    GET    /api/v1/conversations                          — 对话列表
    GET    /api/v1/conversations/{conv_id}/messages       — 对话消息
    DELETE /api/v1/conversations/{conv_id}                — 删除对话
    POST   /api/v1/messages/{msg_id}/feedback             — 消息反馈
"""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException, ValidationException
from app.core.logger import get_logger
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.llm_client import LLMClient
from app.infrastructure.qdrant_client import QdrantStore
from app.models.database.user import User
from app.models.request_response.response import APIResponse, PageInfo, PaginatedData, PaginatedResponse
from app.rag.pipeline import RetrievalPipeline
from app.rag.query_rewriter import QueryRewriter
from app.rag.reranker import Reranker
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.repositories.kb_repository import KBRepository
from app.services.conversation_service import ConversationService
from app.services.rag_service import RAGService

logger = get_logger(__name__)

router = APIRouter(tags=["RAG 问答"])

# AI 服务（延迟初始化单例）
_embedding_client = None
_llm_client = None
_qdrant_store = None
_rag_service = None


def _get_rag_service():
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


def _get_conv_service(db=Depends(get_db)):
    """获取对话服务"""
    return ConversationService(ConversationRepository(db), MessageRepository(db))


class ChatRequest(BaseModel):
    """RAG 问答请求"""
    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    conversation_id: str | None = Field(None, description="对话 ID（多轮对话）")
    top_k: int = Field(50, ge=1, le=100, description="检索候选数")
    temperature: float = Field(0.3, ge=0, le=1, description="LLM 温度")


class FeedbackRequest(BaseModel):
    """消息反馈请求"""
    feedback: str | None = Field(None, pattern="^(positive|negative|null)?$")
    comment: str | None = Field(None)


# ===== RAG 问答 =====

@router.post("/knowledge-bases/{kb_id}/chat", summary="RAG 问答（流式）")
async def rag_chat_stream(
    kb_id: str,
    req: ChatRequest,
    db=Depends(get_db),
):
    """
    RAG 问答 — SSE 流式输出

    事件类型：
        event: token       — 生成的文本片段
        event: metadata    — 对话 ID（多轮对话上下文）
        event: citation    — 引用来源列表
        event: done        — 完成 + 统计信息
        event: error       — 错误信息
    """
    # 校验知识库
    kb_repo = KBRepository(db)
    kb = await kb_repo.find_by_id(UUID(kb_id))
    if not kb:
        raise NotFoundException("知识库", kb_id)

    conv_id = UUID(req.conversation_id) if req.conversation_id else None
    service = _get_rag_service()

    async def event_stream():
        # 发送对话 ID（供前端后续多轮会话使用）
        if conv_id:
            yield f"event: metadata\ndata: {json.dumps({'conversation_id': str(conv_id)})}\n\n"

        async for event in service.ask_stream(req.question, UUID(kb_id), conv_id):
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

    conv_id = UUID(req.conversation_id) if req.conversation_id else None
    service = _get_rag_service()
    result = await service.ask(req.question, UUID(kb_id), conv_id)

    if conv_id:
        result["conversation_id"] = str(conv_id)

    return APIResponse(data=result)


# ===== 对话管理（内联到 rag 路由，简化依赖注入） =====

@router.post("/knowledge-bases/{kb_id}/conversations", summary="创建对话")
async def create_conversation(
    kb_id: str,
    question: str = Query(..., description="第一个问题"),
    current_user: User = Depends(get_current_user),
    conv_service: ConversationService = Depends(_get_conv_service),
) -> APIResponse[dict]:
    """创建新对话（自动生成标题）"""
    result = await conv_service.create_or_get(UUID(kb_id), current_user.id, question)
    return APIResponse(code=201, message="对话创建成功", data=result)


@router.get("/conversations", summary="获取对话列表")
async def list_conversations(
    kb_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    conv_service: ConversationService = Depends(_get_conv_service),
) -> PaginatedResponse[dict]:
    """获取用户对话列表"""
    items, total = await conv_service.list_by_user(
        user_id=current_user.id,
        kb_id=UUID(kb_id) if kb_id else None,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, page_info=PageInfo(total=total, page=page, page_size=page_size))
    )


@router.get("/conversations/{conv_id}/messages", summary="获取对话消息")
async def get_messages(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    conv_service: ConversationService = Depends(_get_conv_service),
) -> APIResponse[list[dict]]:
    """获取对话历史消息"""
    messages = await conv_service.get_messages(UUID(conv_id))
    return APIResponse(data=messages)


@router.delete("/conversations/{conv_id}", summary="删除对话")
async def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    conv_service: ConversationService = Depends(_get_conv_service),
) -> APIResponse[None]:
    """删除对话"""
    await conv_service.delete(UUID(conv_id))
    return APIResponse(message="对话已删除")


@router.post("/messages/{msg_id}/feedback", summary="消息反馈")
async def set_feedback(
    msg_id: str,
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    conv_service: ConversationService = Depends(_get_conv_service),
) -> APIResponse[None]:
    """对消息点赞/点踩"""
    await conv_service.set_feedback(UUID(msg_id), req.feedback, req.comment)
    return APIResponse(message="反馈已提交")
