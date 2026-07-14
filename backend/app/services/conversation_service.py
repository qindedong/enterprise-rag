"""
对话管理服务
"""

import re
from uuid import UUID

from app.core.exceptions import NotFoundException, ValidationException
from app.core.logger import get_logger
from app.repositories.conversation_repository import ConversationRepository, MessageRepository

logger = get_logger(__name__)


class ConversationService:
    """对话管理服务"""

    def __init__(self, conv_repo: ConversationRepository, msg_repo: MessageRepository):
        self.conv_repo = conv_repo
        self.msg_repo = msg_repo

    async def create_or_get(self, kb_id: UUID, user_id: UUID, first_question: str) -> dict:
        """创建新对话（自动提取首问题前50字符作为标题）。如果最近对话存在且活跃则复用。"""
        # 查找最近的活跃对话，5分钟内有活动则复用
        import time
        convs, _ = await self.conv_repo.list_by_user(user_id, kb_id, page=1, page_size=5)
        for conv in convs:
            if conv.status and hasattr(conv.status, 'value'):
                status = conv.status.value if hasattr(conv.status, 'value') else conv.status
            else:
                status = "active"
            if status == "active":
                logger.info(f"复用已有对话: {conv.id}")
                return self._conv_to_dict(conv)

        # 没有活跃对话则创建新的
        title = first_question[:50] + ("..." if len(first_question) > 50 else "")
        conv = await self.conv_repo.create(kb_id=kb_id, user_id=user_id, title=title)
        logger.info(f"对话已创建: {conv.id} — {title}")
        return self._conv_to_dict(conv)

    async def list_by_user(
        self, user_id: UUID, kb_id: UUID | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict], int]:
        """用户对话列表"""
        convs, total = await self.conv_repo.list_by_user(user_id, kb_id, page, page_size)
        return [self._conv_to_dict(c) for c in convs], total

    async def get_messages(self, conv_id: UUID) -> list[dict]:
        """获取对话的所有消息"""
        conv = await self.conv_repo.find_by_id(conv_id)
        if not conv:
            raise NotFoundException("对话", str(conv_id))

        messages = await self.msg_repo.get_by_conversation(conv_id)
        return [
            {
                "id": str(m.id),
                "role": m.role.value if m.role else "user",
                "content": m.content,
                "citations": m.citations,
                "token_usage": m.token_usage,
                "feedback": m.feedback.value if m.feedback else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    async def delete(self, conv_id: UUID) -> None:
        """删除对话"""
        conv = await self.conv_repo.find_by_id(conv_id)
        if not conv:
            raise NotFoundException("对话", str(conv_id))
        await self.conv_repo.delete(conv_id)
        logger.info(f"对话已删除: {conv_id}")

    async def add_message(
        self, conv_id: UUID, role: str, content: str,
        citations: list | None = None, token_usage: dict | None = None,
    ) -> dict:
        """添加消息到对话"""
        msg = await self.msg_repo.create(
            conversation_id=conv_id,
            role=role,
            content=content,
            citations=citations,
            token_usage=token_usage,
        )
        await self.conv_repo.update_message_count(conv_id)
        return {
            "id": str(msg.id),
            "role": role,
            "content": content,
            "created_at": msg.created_at.isoformat() if msg.created_at else None,
        }

    async def set_feedback(self, msg_id: UUID, feedback: str | None, comment: str | None = None) -> None:
        """设置消息反馈"""
        await self.msg_repo.set_feedback(msg_id, feedback, comment)
        logger.info(f"消息反馈已设置: msg={msg_id} feedback={feedback}")

    def _conv_to_dict(self, conv) -> dict:
        return {
            "id": str(conv.id),
            "kb_id": str(conv.kb_id) if conv.kb_id else None,
            "title": conv.title,
            "message_count": conv.message_count or 0,
            "status": conv.status.value if conv.status else "active",
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        }
