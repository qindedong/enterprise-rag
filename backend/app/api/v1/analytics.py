"""
数据分析看板 API 接口

路由：
    GET /api/v1/analytics/overview — 全局数据总览（跨用户可访问的全部知识库）
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import get_current_user, get_db
from app.core.logger import get_logger
from app.models.database.conversation import Conversation, Message, MsgFeedback, MsgRole
from app.models.database.document import DocStatus, Document
from app.models.database.knowledge_base import KBMember, KBStatus, KnowledgeBase
from app.models.database.user import User, UserRole
from app.models.request_response.response import APIResponse

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["数据分析"])


async def _accessible_kb_ids(db, user: User) -> list[UUID]:
    """用户可访问的知识库 ID 列表（全局 admin 为全部）"""
    if user.role in (UserRole.SUPER_ADMIN, UserRole.ADMIN):
        result = await db.execute(
            select(KnowledgeBase.id).where(KnowledgeBase.status != KBStatus.DELETED)
        )
        return [row[0] for row in result.all()]

    owned = select(KnowledgeBase.id).where(
        KnowledgeBase.owner_id == user.id, KnowledgeBase.status != KBStatus.DELETED
    )
    member_of = select(KBMember.kb_id).where(KBMember.user_id == user.id)
    kb_ids = owned.union(member_of).subquery()
    result = await db.execute(select(kb_ids.c.id))
    return [row[0] for row in result.all()]


@router.get("/overview", summary="数据总览")
async def analytics_overview(
    days: int = Query(30, ge=1, le=90, description="趋势统计天数"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_db),
):
    """跨知识库的数据总览：总量、问答趋势、各知识库明细、反馈满意率"""
    kb_ids = await _accessible_kb_ids(db, current_user)
    if not kb_ids:
        return APIResponse(
            data={
                "totals": {
                    "kb_count": 0,
                    "doc_count": 0,
                    "conversation_count": 0,
                    "question_count": 0,
                    "positive": 0,
                    "negative": 0,
                    "satisfaction_rate": None,
                },
                "daily_questions": [],
                "kb_breakdown": [],
            }
        )

    # ===== 总量 =====
    doc_count = (
        await db.execute(
            select(func.count()).where(
                Document.kb_id.in_(kb_ids), Document.status != DocStatus.DELETED
            )
        )
    ).scalar() or 0

    conv_count = (
        await db.execute(select(func.count()).where(Conversation.kb_id.in_(kb_ids)))
    ).scalar() or 0

    # 问答数（user 角色消息数）
    question_count = (
        await db.execute(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.kb_id.in_(kb_ids), Message.role == MsgRole.USER)
        )
    ).scalar() or 0

    # 反馈
    fb_rows = (
        await db.execute(
            select(Message.feedback, func.count())
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.kb_id.in_(kb_ids), Message.feedback.is_not(None))
            .group_by(Message.feedback)
        )
    ).all()
    fb_counts = {str(row[0]): row[1] for row in fb_rows}
    positive = fb_counts.get(MsgFeedback.POSITIVE.value, 0)
    negative = fb_counts.get(MsgFeedback.NEGATIVE.value, 0)
    fb_total = positive + negative
    satisfaction = round(positive / fb_total * 100, 1) if fb_total > 0 else None

    # ===== 按天问答趋势 =====
    since = datetime.now(UTC) - timedelta(days=days - 1)
    day = func.date(Message.created_at)
    daily_rows = (
        await db.execute(
            select(day, func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.kb_id.in_(kb_ids),
                Message.role == MsgRole.USER,
                Message.created_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )
    ).all()
    daily_questions = [
        {
            # PostgreSQL 返回 date 对象，SQLite 返回字符串
            "date": d.isoformat() if hasattr(d, "isoformat") else str(d),
            "count": c,
        }
        for d, c in daily_rows
    ]

    # ===== 各知识库明细 =====
    kb_rows = (
        (await db.execute(select(KnowledgeBase).where(KnowledgeBase.id.in_(kb_ids))))
        .scalars()
        .all()
    )

    doc_counts = dict(
        (
            await db.execute(
                select(Document.kb_id, func.count())
                .where(Document.kb_id.in_(kb_ids), Document.status != DocStatus.DELETED)
                .group_by(Document.kb_id)
            )
        ).all()
    )
    q_counts = dict(
        (
            await db.execute(
                select(Conversation.kb_id, func.count())
                .select_from(Message)
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(Conversation.kb_id.in_(kb_ids), Message.role == MsgRole.USER)
                .group_by(Conversation.kb_id)
            )
        ).all()
    )
    fb_by_kb = (
        await db.execute(
            select(Conversation.kb_id, Message.feedback, func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(Conversation.kb_id.in_(kb_ids), Message.feedback.is_not(None))
            .group_by(Conversation.kb_id, Message.feedback)
        )
    ).all()
    kb_fb: dict[UUID, dict] = {}
    for kb_id, fb, cnt in fb_by_kb:
        kb_fb.setdefault(kb_id, {})[str(fb)] = cnt

    kb_breakdown = []
    for kb in kb_rows:
        fbc = kb_fb.get(kb.id, {})
        pos = fbc.get(MsgFeedback.POSITIVE.value, 0)
        neg = fbc.get(MsgFeedback.NEGATIVE.value, 0)
        tot = pos + neg
        kb_breakdown.append(
            {
                "kb_id": str(kb.id),
                "name": kb.name,
                "doc_count": doc_counts.get(kb.id, 0),
                "question_count": q_counts.get(kb.id, 0),
                "satisfaction_rate": round(pos / tot * 100, 1) if tot > 0 else None,
            }
        )
    kb_breakdown.sort(key=lambda x: x["question_count"], reverse=True)

    return APIResponse(
        data={
            "totals": {
                "kb_count": len(kb_ids),
                "doc_count": doc_count,
                "conversation_count": conv_count,
                "question_count": question_count,
                "positive": positive,
                "negative": negative,
                "satisfaction_rate": satisfaction,
            },
            "daily_questions": daily_questions,
            "kb_breakdown": kb_breakdown,
        }
    )
