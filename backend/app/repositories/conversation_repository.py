"""
对话数据访问层
"""

from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.database.conversation import Conversation, Message, ConvStatus, MsgFeedback


class ConversationRepository:
    """对话会话数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, kb_id: UUID, user_id: UUID, title: str | None = None) -> Conversation:
        """创建对话"""
        conv = Conversation(kb_id=kb_id, user_id=user_id, title=title)
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def find_by_id(self, conv_id: UUID) -> Conversation | None:
        """按 ID 查找"""
        result = await self.session.execute(
            select(Conversation)
            .options(joinedload(Conversation.messages))
            .where(Conversation.id == conv_id, Conversation.status != ConvStatus.ARCHIVED)
        )
        return result.unique().scalar_one_or_none()

    async def list_by_user(
        self, user_id: UUID, kb_id: UUID | None = None, page: int = 1, page_size: int = 20
    ) -> tuple[list[Conversation], int]:
        """分页查询用户的对话列表"""
        conditions = [
            Conversation.user_id == user_id,
            Conversation.status == ConvStatus.ACTIVE,
        ]
        if kb_id:
            conditions.append(Conversation.kb_id == kb_id)

        count_q = select(func.count()).where(and_(*conditions))
        total = (await self.session.execute(count_q)).scalar() or 0

        q = (
            select(Conversation)
            .where(and_(*conditions))
            .order_by(Conversation.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(q)
        return list(result.scalars().all()), total

    async def delete(self, conv_id: UUID) -> None:
        """软删除对话（级联消息由 ondelete=CASCADE 处理）"""
        from sqlalchemy import update as sql_update
        from datetime import datetime, timezone

        await self.session.execute(
            sql_update(Conversation)
            .where(Conversation.id == conv_id)
            .values(status=ConvStatus.ARCHIVED, updated_at=datetime.now(timezone.utc))
        )

    async def update_message_count(self, conv_id: UUID) -> None:
        """更新消息计数"""
        from sqlalchemy import update as sql_update
        from datetime import datetime, timezone

        count = await self.session.execute(
            select(func.count()).where(Message.conversation_id == conv_id)
        )
        total = count.scalar() or 0
        await self.session.execute(
            sql_update(Conversation)
            .where(Conversation.id == conv_id)
            .values(message_count=total, updated_at=datetime.now(timezone.utc))
        )


class MessageRepository:
    """消息数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
        citations: list | None = None,
        token_usage: dict | None = None,
    ) -> Message:
        """创建消息"""
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations or [],
            token_usage=token_usage or {},
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_by_conversation(self, conv_id: UUID) -> list[Message]:
        """获取对话的所有消息（按时间排序）"""
        result = await self.session.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def set_feedback(self, msg_id: UUID, feedback: str | None, comment: str | None = None) -> None:
        """设置消息反馈"""
        from sqlalchemy import update as sql_update

        fb = MsgFeedback(feedback) if feedback else None
        await self.session.execute(
            sql_update(Message)
            .where(Message.id == msg_id)
            .values(feedback=fb, feedback_comment=comment)
        )
