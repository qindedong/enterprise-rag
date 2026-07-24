"""数据分析看板测试 — GET /analytics/overview"""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.main import app
from app.repositories.conversation_repository import ConversationRepository, MessageRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.kb_repository import KBRepository


async def _seed_kb_with_activity(db_session: AsyncSession, owner_id, name="看板库"):
    """创建知识库 + 文档 + 一轮问答 + 一条正反馈"""
    kb_repo = KBRepository(db_session)
    doc_repo = DocumentRepository(db_session)
    conv_repo = ConversationRepository(db_session)
    msg_repo = MessageRepository(db_session)

    kb = await kb_repo.create(name=name, owner_id=owner_id)
    await db_session.commit()

    await doc_repo.create(kb_id=kb.id, title=f"{name}文档.pdf", file_type="pdf")
    await db_session.commit()

    conv = await conv_repo.create(kb_id=kb.id, user_id=owner_id, title="t")
    await db_session.commit()
    await msg_repo.create(conversation_id=conv.id, role="user", content="问题")
    ans = await msg_repo.create(conversation_id=conv.id, role="assistant", content="回答")
    await db_session.commit()
    await msg_repo.set_feedback(ans.id, "positive")
    await db_session.commit()
    return kb


def _override(app_user, db_session):
    async def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: app_user


@pytest.mark.unit
class TestAnalyticsOverview:
    """GET /api/v1/analytics/overview"""

    @pytest.mark.asyncio
    async def test_overview_totals_and_breakdown(self, db_session: AsyncSession):
        """总量统计 + 各知识库明细，且只包含有权限的库"""
        user = MagicMock()
        user.id = uuid4()
        user.role = "user"

        await _seed_kb_with_activity(db_session, user.id, "我的库")
        # 别人的库不应计入
        await _seed_kb_with_activity(db_session, uuid4(), "别人的库")

        _override(user, db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/analytics/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        totals = data["totals"]
        assert totals["kb_count"] == 1
        assert totals["doc_count"] == 1
        assert totals["question_count"] == 1
        assert totals["positive"] == 1
        assert totals["satisfaction_rate"] == 100.0
        assert len(data["kb_breakdown"]) == 1
        assert data["kb_breakdown"][0]["name"] == "我的库"
        assert len(data["daily_questions"]) >= 1

    @pytest.mark.asyncio
    async def test_overview_empty_for_new_user(self, db_session: AsyncSession):
        """无任何知识库时返回空结构，不报错"""
        user = MagicMock()
        user.id = uuid4()
        user.role = "user"

        _override(user, db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/analytics/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["totals"]["kb_count"] == 0
        assert data["totals"]["satisfaction_rate"] is None
        assert data["daily_questions"] == []

    @pytest.mark.asyncio
    async def test_overview_admin_sees_all(self, db_session: AsyncSession):
        """全局 admin 可见全部知识库"""
        await _seed_kb_with_activity(db_session, uuid4(), "库A")
        await _seed_kb_with_activity(db_session, uuid4(), "库B")

        admin = MagicMock()
        admin.id = uuid4()
        admin.role = "super_admin"

        _override(admin, db_session)
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/analytics/overview")
        finally:
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["totals"]["kb_count"] >= 2
        names = {k["name"] for k in data["kb_breakdown"]}
        assert {"库A", "库B"} <= names
