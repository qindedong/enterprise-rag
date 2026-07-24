"""反馈分析测试 — MessageRepository 统计方法 + 反馈统计 API"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.main import app
from app.models.database.knowledge_base import KnowledgeBase
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.repositories.kb_repository import KBRepository


async def _create_test_kb(db_session: AsyncSession) -> KnowledgeBase:
    repo = KBRepository(db_session)
    kb = await repo.create(name="反馈测试库", owner_id=uuid4())
    await db_session.commit()
    return kb


async def _seed_feedback(db_session, kb, feedbacks: list[tuple[str | None, str | None]]):
    """创建对话 + 带反馈的 assistant 消息"""
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)
    conv = await conv_repo.create(kb_id=kb.id, user_id=uuid4(), title="t")
    await db_session.commit()
    msgs = []
    for fb, comment in feedbacks:
        msg = await msg_repo.create(conversation_id=conv.id, role="assistant", content="回答内容")
        await db_session.commit()
        if fb:
            await msg_repo.set_feedback(msg.id, fb, comment)
            await db_session.commit()
        msgs.append(msg)
    return conv, msgs


@pytest.mark.unit
class TestFeedbackStatsRepository:
    """反馈统计查询"""

    @pytest.mark.asyncio
    async def test_feedback_totals(self, db_session: AsyncSession):
        """统计正/负反馈总数"""
        kb = await _create_test_kb(db_session)
        await _seed_feedback(
            db_session,
            kb,
            [("positive", None), ("positive", None), ("negative", "不好"), (None, None)],
        )
        repo = MessageRepository(db_session)
        positive, negative = await repo.feedback_totals(kb.id)
        assert positive == 2
        assert negative == 1

    @pytest.mark.asyncio
    async def test_feedback_totals_excludes_other_kb(self, db_session: AsyncSession):
        """统计只包含目标知识库"""
        kb1 = await _create_test_kb(db_session)
        kb2 = await _create_test_kb(db_session)
        await _seed_feedback(db_session, kb1, [("positive", None)])
        await _seed_feedback(db_session, kb2, [("negative", None), ("negative", None)])
        repo = MessageRepository(db_session)
        positive, negative = await repo.feedback_totals(kb1.id)
        assert positive == 1
        assert negative == 0

    @pytest.mark.asyncio
    async def test_feedback_daily_counts(self, db_session: AsyncSession):
        """按天统计反馈趋势"""
        kb = await _create_test_kb(db_session)
        await _seed_feedback(db_session, kb, [("positive", None), ("negative", None)])
        repo = MessageRepository(db_session)
        since = datetime.now(UTC) - timedelta(days=7)
        rows = await repo.feedback_daily_counts(kb.id, since)
        assert len(rows) >= 1
        total = sum(r[2] for r in rows)
        assert total == 2

    @pytest.mark.asyncio
    async def test_recent_negative_feedback(self, db_session: AsyncSession):
        """最近负反馈按时间倒序，含备注"""
        kb = await _create_test_kb(db_session)
        await _seed_feedback(
            db_session, kb, [("positive", None), ("negative", "答案错误"), ("negative", "答非所问")]
        )
        repo = MessageRepository(db_session)
        msgs = await repo.recent_negative_feedback(kb.id, limit=10)
        assert len(msgs) == 2
        comments = {m.feedback_comment for m in msgs}
        assert comments == {"答案错误", "答非所问"}
        assert msgs[0].created_at >= msgs[1].created_at


@pytest.mark.unit
class TestFeedbackStatsAPI:
    """反馈统计 API"""

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, db_session: AsyncSession):
        """GET /feedback/stats 返回满意率与趋势结构"""
        kb = await _create_test_kb(db_session)
        await _seed_feedback(db_session, kb, [("positive", None), ("negative", "不准")])

        mock_user = MagicMock()
        mock_user.id = uuid4()

        async def _override_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/knowledge-bases/{kb.id}/feedback/stats",
                    headers={"Authorization": "Bearer fake"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 2
        assert data["positive"] == 1
        assert data["negative"] == 1
        assert data["satisfaction_rate"] == 50.0
        assert isinstance(data["daily"], list)
        assert len(data["recent_negative"]) == 1
        assert data["recent_negative"][0]["comment"] == "不准"

    @pytest.mark.asyncio
    async def test_stats_empty_kb(self, db_session: AsyncSession):
        """无反馈时满意率为 null，不报错"""
        kb = await _create_test_kb(db_session)

        mock_user = MagicMock()
        mock_user.id = uuid4()

        async def _override_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_db
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get(
                    f"/api/v1/knowledge-bases/{kb.id}/feedback/stats",
                    headers={"Authorization": "Bearer fake"},
                )
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["satisfaction_rate"] is None
