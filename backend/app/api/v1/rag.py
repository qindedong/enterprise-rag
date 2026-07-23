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
import time
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
from app.models.request_response.response import (
    APIResponse,
    PageInfo,
    PaginatedData,
    PaginatedResponse,
)
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
        from app.core.database import async_session
        from app.rag.bm25_retriever import BM25Retriever

        _embedding_client = EmbeddingClient()
        _llm_client = LLMClient()
        _qdrant_store = QdrantStore()

        query_rewriter = QueryRewriter(_llm_client)
        reranker = Reranker()
        bm25_retriever = BM25Retriever(async_session)
        retrieval_pipeline = RetrievalPipeline(
            _embedding_client, _qdrant_store, query_rewriter, reranker, bm25_retriever
        )
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


class SearchRequest(BaseModel):
    """独立检索请求（只检索不生成）"""

    question: str = Field(..., min_length=1, max_length=2000, description="检索问题")
    top_k: int = Field(10, ge=1, le=50, description="重排后返回数量")
    candidate_k: int = Field(50, ge=1, le=100, description="向量检索候选数")
    mode: str = Field("vector", pattern="^(vector|bm25|hybrid)$", description="检索模式")


class FeedbackRequest(BaseModel):
    """消息反馈请求"""

    feedback: str | None = Field(None, pattern="^(positive|negative|null)?$")
    comment: str | None = Field(None)


# ===== RAG 问答 =====


async def _load_history(db, conv_id: UUID | None) -> list[dict] | None:
    """加载对话历史（多轮对话上下文）"""
    if conv_id is None:
        return None
    msg_repo = MessageRepository(db)
    messages = await msg_repo.get_by_conversation(conv_id)
    if not messages:
        return None
    return [{"role": m.role.value if m.role else "user", "content": m.content} for m in messages]


async def _save_turn(db, conv_id: UUID | None, question: str, answer: str, citations: list) -> None:
    """保存一轮问答到对话历史（best-effort，失败不影响回答）"""
    if conv_id is None or not answer:
        return
    try:
        conv_service = ConversationService(ConversationRepository(db), MessageRepository(db))
        await conv_service.add_message(conv_id, "user", question)
        await conv_service.add_message(conv_id, "assistant", answer, citations=citations)
    except Exception as e:
        logger.warning(f"对话消息保存失败（不影响回答）: {e}")


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
    history = await _load_history(db, conv_id)
    # 释放事务/连接：后续 LLM 生成耗时不占用连接池（高并发关键）
    await db.commit()

    async def event_stream():
        # 发送对话 ID（供前端后续多轮会话使用）
        if conv_id:
            yield f"event: metadata\ndata: {json.dumps({'conversation_id': str(conv_id)})}\n\n"

        # 累积答案与引用，流结束后落库
        full_answer = ""
        citations: list = []
        async for event in service.ask_stream(req.question, UUID(kb_id), conv_id, history):
            if event.startswith("event: token"):
                try:
                    data = json.loads(event.split("data: ", 1)[1])
                    full_answer += data.get("content", "")
                except (IndexError, json.JSONDecodeError):
                    pass
            elif event.startswith("event: citation"):
                try:
                    data = json.loads(event.split("data: ", 1)[1])
                    citations = data.get("citations", [])
                except (IndexError, json.JSONDecodeError):
                    pass
            yield event

        # 多轮对话：保存本轮问答
        await _save_turn(db, conv_id, req.question, full_answer, citations)

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
    history = await _load_history(db, conv_id)
    # 释放事务/连接：后续 LLM 生成耗时不占用连接池（高并发关键）
    await db.commit()
    result = await service.ask(req.question, UUID(kb_id), conv_id, history)

    if conv_id:
        result["conversation_id"] = str(conv_id)
        await _save_turn(db, conv_id, req.question, result["answer"], result["citations"])

    return APIResponse(data=result)


# ===== 独立检索（只检索不生成，供评估/调试使用） =====


@router.post("/knowledge-bases/{kb_id}/search", summary="独立检索（不生成答案）")
async def rag_search(
    kb_id: str,
    req: SearchRequest,
    db=Depends(get_db),
) -> APIResponse[dict]:
    """
    独立检索 API — 只执行检索管线，不调用 LLM 生成

    用于检索效果评估（Recall@K / MRR）与检索结果调试。

    mode 说明：
        vector — 纯向量检索（Qdrant）
        bm25   — 纯全文检索（PostgreSQL tsvector + jieba）
        hybrid — 向量 + BM25，RRF 融合
    """
    kb_repo = KBRepository(db)
    kb = await kb_repo.find_by_id(UUID(kb_id))
    if not kb:
        raise NotFoundException("知识库", kb_id)
    # 释放事务/连接：后续检索+LLM 改写耗时不占用连接池（高并发关键）
    await db.commit()

    start = time.time()
    service = _get_rag_service()
    try:
        docs = await service.retrieval.retrieve(
            req.question,
            UUID(kb_id),
            retrieval_top_k=req.candidate_k,
            rerank_top_k=req.top_k,
            mode=req.mode,
        )
    except ValueError as e:
        raise ValidationException(str(e)) from e
    elapsed = (time.time() - start) * 1000

    results = [
        {
            "rank": i + 1,
            "chunk_id": doc.get("chunk_id", ""),
            "document_title": doc.get("document_title", doc.get("title", "未知文档")),
            "content": doc.get("content", ""),
            "page_number": doc.get("page_number"),
            "score": doc.get("score", 0),
        }
        for i, doc in enumerate(docs)
    ]

    return APIResponse(
        data={
            "question": req.question,
            "mode": req.mode,
            "kb_id": kb_id,
            "results": results,
            "total": len(results),
            "processing_time_ms": elapsed,
        }
    )


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
        data=PaginatedData(
            items=items, page_info=PageInfo(total=total, page=page, page_size=page_size)
        )
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
