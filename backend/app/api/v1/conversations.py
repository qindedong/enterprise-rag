"""
对话管理 API 接口
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundException
from app.models.database.user import User
from app.models.request_response.response import APIResponse, PageInfo, PaginatedData, PaginatedResponse
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.repositories.kb_repository import KBRepository
from app.services.conversation_service import ConversationService

router = APIRouter(tags=["对话管理"])


def get_conv_service(db=Depends(get_db)):
    return ConversationService(ConversationRepository(db), MessageRepository(db))


class FeedbackRequest(BaseModel):
    feedback: str | None = Field(None, pattern="^(positive|negative|null)?$")
    comment: str | None = Field(None)


@router.post("/knowledge-bases/{kb_id}/conversations", summary="创建对话")
async def create_conversation(
    kb_id: str,
    question: str = Query(..., description="第一个问题"),
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conv_service),
) -> APIResponse[dict]:
    """创建新对话"""
    result = await service.create_or_get(UUID(kb_id), current_user.id, question)
    return APIResponse(code=201, message="对话创建成功", data=result)


@router.get("/conversations", summary="获取对话列表")
async def list_conversations(
    kb_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conv_service),
) -> PaginatedResponse[dict]:
    """获取用户对话列表"""
    items, total = await service.list_by_user(
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
    service: ConversationService = Depends(get_conv_service),
) -> APIResponse[list[dict]]:
    """获取对话历史消息"""
    messages = await service.get_messages(UUID(conv_id))
    return APIResponse(data=messages)


@router.delete("/conversations/{conv_id}", summary="删除对话")
async def delete_conversation(
    conv_id: str,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conv_service),
) -> APIResponse[None]:
    """删除对话"""
    await service.delete(UUID(conv_id))
    return APIResponse(message="对话已删除")


@router.post("/messages/{msg_id}/feedback", summary="消息反馈")
async def set_feedback(
    msg_id: str,
    req: FeedbackRequest,
    current_user: User = Depends(get_current_user),
    service: ConversationService = Depends(get_conv_service),
) -> APIResponse[None]:
    """对消息点赞/点踩"""
    await service.set_feedback(UUID(msg_id), req.feedback, req.comment)
    return APIResponse(message="反馈已提交")
