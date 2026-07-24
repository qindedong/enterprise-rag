"""
反馈分析 API 接口

路由：
    GET /api/v1/knowledge-bases/{kb_id}/feedback/stats — 反馈统计（满意率 + 趋势 + 负反馈明细）
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.logger import get_logger
from app.core.rbac import require_kb_role
from app.models.database.knowledge_base import MemberRole
from app.models.request_response.response import APIResponse
from app.repositories.conversation_repository import MessageRepository

logger = get_logger(__name__)

router = APIRouter(tags=["反馈分析"])


@router.get("/knowledge-bases/{kb_id}/feedback/stats", summary="反馈统计")
async def feedback_stats(
    kb_id: str,
    days: int = Query(30, ge=1, le=90, description="趋势统计天数"),
    _kb=Depends(require_kb_role(MemberRole.VIEWER)),
    db=Depends(get_db),
):
    """知识库问答反馈分析：满意率、按天趋势、最近负反馈明细（需 viewer 及以上权限）"""
    msg_repo = MessageRepository(db)

    positive, negative = await msg_repo.feedback_totals(UUID(kb_id))
    total = positive + negative
    satisfaction = round(positive / total * 100, 1) if total > 0 else None

    since = datetime.now(UTC) - timedelta(days=days - 1)
    rows = await msg_repo.feedback_daily_counts(UUID(kb_id), since)
    daily_map: dict[str, dict] = {}
    for day, feedback, count in rows:
        # PostgreSQL 返回 date 对象，SQLite 返回字符串
        key = day.isoformat() if hasattr(day, "isoformat") else str(day)
        entry = daily_map.setdefault(key, {"date": key, "positive": 0, "negative": 0})
        entry[str(feedback)] = count
    daily = [daily_map[k] for k in sorted(daily_map)]

    recent = await msg_repo.recent_negative_feedback(UUID(kb_id), limit=10)
    recent_negative = [
        {
            "message_id": str(m.id),
            "conversation_id": str(m.conversation_id),
            "answer_preview": m.content[:120],
            "comment": m.feedback_comment,
            "created_at": m.created_at.isoformat(),
        }
        for m in recent
    ]

    return APIResponse(
        data={
            "total": total,
            "positive": positive,
            "negative": negative,
            "satisfaction_rate": satisfaction,
            "daily": daily,
            "recent_negative": recent_negative,
        }
    )
