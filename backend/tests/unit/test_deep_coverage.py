"""API + Service 层纵深覆盖测试 — 纯 Mock 版（无外部依赖）"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# ============================================================
# AuthService — login / refresh / get_current_user 全覆盖
# ============================================================


@pytest.mark.unit
class TestAuthServiceCoverage:
    """补充 auth_service.py 中剩余路径"""

    @pytest.mark.asyncio
    async def test_login_inactive_user_raises(self):
        """测试：已禁用用户登录"""
        from app.core.exceptions import UnauthorizedException
        from app.services.auth_service import AuthService

        mock_user = MagicMock()
        mock_user.hashed_password = "hashed"
        mock_user.is_active = False

        user_repo = AsyncMock()
        user_repo.find_by_email = AsyncMock(return_value=mock_user)

        with patch("app.services.auth_service.verify_password", return_value=True):
            service = AuthService(user_repo)
            with pytest.raises(UnauthorizedException):
                await service.login("inactive@test.com", "password")

    @pytest.mark.asyncio
    async def test_login_success_full(self):
        """测试：登录成功完整路径"""
        from app.services.auth_service import AuthService

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.username = "alice"
        mock_user.email = "alice@test.com"
        mock_user.display_name = "Alice"
        mock_user.role = MagicMock(value="user")
        mock_user.is_active = True
        mock_user.hashed_password = "hashed"

        user_repo = AsyncMock()
        user_repo.find_by_email = AsyncMock(return_value=mock_user)
        user_repo.update_last_login = AsyncMock()

        with patch("app.services.auth_service.verify_password", return_value=True):
            with patch("app.services.auth_service.create_access_token", return_value="access"):
                with patch(
                    "app.services.auth_service.create_refresh_token", return_value="refresh"
                ):
                    service = AuthService(user_repo)
                    result = await service.login("alice@test.com", "any")
                    assert result["access_token"] == "access"
                    assert result["token_type"] == "bearer"
                    assert user_repo.update_last_login.called

    @pytest.mark.asyncio
    async def test_refresh_token_success(self):
        """测试：Refresh Token 成功"""
        from app.services.auth_service import AuthService

        mock_user = MagicMock()
        mock_user.id = uuid4()
        mock_user.username = "bob"
        mock_user.is_active = True
        mock_user.role = MagicMock(value="user")

        user_repo = AsyncMock()
        user_repo.find_by_id = AsyncMock(return_value=mock_user)

        with patch(
            "app.services.auth_service.decode_token",
            return_value={"sub": str(uuid4()), "type": "refresh"},
        ):
            with patch("app.services.auth_service.create_access_token", return_value="new_access"):
                with patch(
                    "app.services.auth_service.create_refresh_token", return_value="new_refresh"
                ):
                    service = AuthService(user_repo)
                    result = await service.refresh_token("valid_refresh")
                    assert result["access_token"] == "new_access"
                    assert result["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_get_current_user_success(self):
        """测试：get_current_user 成功"""
        from app.services.auth_service import AuthService

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.username = "alice"

        user_repo = AsyncMock()
        user_repo.find_by_id = AsyncMock(return_value=mock_user)

        service = AuthService(user_repo)
        result = await service.get_current_user(str(uuid4()))
        assert result.username == "alice"


# ============================================================
# RAGService 流式全覆盖
# ============================================================


@pytest.mark.unit
class TestRAGServiceStream:
    """RAGService ask_stream 完整测试"""

    @pytest.mark.asyncio
    async def test_ask_stream_empty_docs(self):
        """测试：空检索发 error"""
        from app.services.rag_service import RAGService

        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(return_value=[])

        service = RAGService(mock_retrieval, AsyncMock())
        events = []
        async for event in service.ask_stream("问题", uuid4()):
            events.append(event)

        assert any("error" in e for e in events)

    @pytest.mark.asyncio
    async def test_ask_stream_normal(self):
        """测试：正常流式"""
        from app.services.rag_service import RAGService

        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(
            return_value=[
                {
                    "document_title": "手册",
                    "content": "内容",
                    "chunk_id": str(uuid4()),
                    "score": 0.8,
                }
            ]
        )

        mock_llm = AsyncMock()

        async def token_stream(*args, **kwargs):
            yield "答案1"
            yield "答案2"

        mock_llm.generate_stream = token_stream

        service = RAGService(mock_retrieval, mock_llm)
        events = []
        async for event in service.ask_stream("问题", uuid4()):
            events.append(event)

        assert any("token" in e for e in events)
        assert any("citation" in e for e in events)
        assert any("done" in e for e in events)

    @pytest.mark.asyncio
    async def test_ask_stream_exception(self):
        """测试：LLM 异常发 error"""
        from app.services.rag_service import RAGService

        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(
            return_value=[
                {
                    "document_title": "手册",
                    "content": "内容",
                    "chunk_id": str(uuid4()),
                    "score": 0.8,
                }
            ]
        )

        async def failing_stream(*args, **kwargs):
            raise RuntimeError("LLM 崩溃")
            yield

        mock_llm = AsyncMock()
        mock_llm.generate_stream = failing_stream

        service = RAGService(mock_retrieval, mock_llm)
        events = []
        async for event in service.ask_stream("问题", uuid4()):
            events.append(event)

        assert any("error" in e for e in events)


# ============================================================
# DocumentService — 纯 Mock 无网络
# ============================================================


@pytest.mark.unit
class TestDocumentServiceDeep:
    """DocumentService 补充"""

    def test_to_response_enum(self):
        """测试：_to_response Enum 处理"""
        from app.models.database.document import DocStatus, DocType
        from app.services.document_service import DocumentService

        mock_doc = MagicMock()
        mock_doc.id = uuid4()
        mock_doc.kb_id = uuid4()
        mock_doc.title = "测试.pdf"
        mock_doc.file_type = DocType.PDF
        mock_doc.file_size = 1024
        mock_doc.status = DocStatus.COMPLETED
        mock_doc.chunk_count = 5
        mock_doc.error_message = None
        mock_doc.created_at = None
        mock_doc.updated_at = None

        service = DocumentService(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
        result = service._to_response(mock_doc)

        assert result["file_type"] == "pdf"
        assert result["status"] == "completed"
        assert result["chunk_count"] == 5


# ============================================================
# ConversationService — create_or_get 复用 / get_messages
# ============================================================


@pytest.mark.unit
class TestConversationServiceCoverage:
    """ConversationService 补充"""

    @pytest.mark.asyncio
    async def test_create_or_get_reuses_active(self):
        """测试：复用已有活跃对话"""
        from app.services.conversation_service import ConversationService

        mock_conv = AsyncMock()
        mock_conv.id = uuid4()
        mock_conv.kb_id = uuid4()
        mock_conv.title = "已有"
        mock_conv.message_count = 3
        mock_conv.status = MagicMock(value="active")
        mock_conv.created_at = None
        mock_conv.updated_at = None

        conv_repo = AsyncMock()
        conv_repo.list_by_user = AsyncMock(return_value=([mock_conv], 1))

        service = ConversationService(conv_repo, AsyncMock())
        result = await service.create_or_get(uuid4(), uuid4(), "新问题")

        assert result["title"] == "已有"
        assert not conv_repo.create.called

    @pytest.mark.asyncio
    async def test_get_messages_with_data(self):
        """测试：获取消息列表"""
        from app.services.conversation_service import ConversationService

        mock_msg = AsyncMock()
        mock_msg.id = uuid4()
        mock_msg.role = MagicMock(value="user")
        mock_msg.content = "用户问题"
        mock_msg.citations = []
        mock_msg.token_usage = {}
        mock_msg.feedback = None
        mock_msg.created_at = None

        msg_repo = AsyncMock()
        msg_repo.get_by_conversation = AsyncMock(return_value=[mock_msg])

        conv_repo = AsyncMock()
        conv_repo.find_by_id = AsyncMock(return_value=MagicMock())

        service = ConversationService(conv_repo, msg_repo)
        messages = await service.get_messages(uuid4())

        assert len(messages) == 1
        assert messages[0]["role"] == "user"


# ============================================================
# KBService — 全部路径
# ============================================================


@pytest.mark.unit
class TestKBServiceCoverage:
    """KBService 全面覆盖"""

    @pytest.mark.asyncio
    async def test_get_detail_with_stats(self):
        """测试：获取含统计的详情"""
        from app.services.kb_service import KBService

        mock_owner = MagicMock()
        mock_owner.id = uuid4()
        mock_owner.display_name = "Owner"

        mock_kb = MagicMock()
        mock_kb.id = uuid4()
        mock_kb.name = "统计库"
        mock_kb.description = "desc"
        mock_kb.owner = mock_owner
        mock_kb.chunk_size = 500
        mock_kb.chunk_overlap = 100
        mock_kb.embedding_model = "bge"
        mock_kb.status = MagicMock(value="active")
        mock_kb.created_at = None
        mock_kb.updated_at = None

        kb_repo = AsyncMock()
        kb_repo.find_by_id_with_owner = AsyncMock(return_value=mock_kb)
        kb_repo.is_member = AsyncMock(return_value=True)
        kb_repo.get_document_count = AsyncMock(return_value=10)
        kb_repo.get_chunk_count = AsyncMock(return_value=50)
        kb_repo.count_members = AsyncMock(return_value=3)

        service = KBService(kb_repo)
        result = await service.get_detail(uuid4(), uuid4())

        assert result["name"] == "统计库"
        assert result["stats"]["document_count"] == 10
        assert result["stats"]["chunk_count"] == 50
        assert result["member_count"] == 3

    @pytest.mark.asyncio
    async def test_update_kb_success(self):
        """测试：成功更新"""
        from app.services.kb_service import KBService

        owner_id = uuid4()
        mock_kb = MagicMock()
        mock_kb.id = uuid4()
        mock_kb.owner_id = owner_id

        mock_updated = MagicMock()
        mock_updated.id = mock_kb.id
        mock_updated.name = "new_name"
        mock_updated.description = ""
        mock_updated.owner_id = owner_id
        mock_updated.status = MagicMock(value="active")
        mock_updated.created_at = None
        mock_updated.updated_at = None

        kb_repo = AsyncMock()
        kb_repo.find_by_id = AsyncMock(side_effect=[mock_kb, mock_updated])

        service = KBService(kb_repo)
        result = await service.update(mock_kb.id, owner_id, name="new_name")
        assert result["name"] == "new_name"

    @pytest.mark.asyncio
    async def test_add_member_success(self):
        """测试：成功添加成员"""
        from app.services.kb_service import KBService

        owner_id = uuid4()
        mock_kb = MagicMock()
        mock_kb.id = uuid4()
        mock_kb.owner_id = owner_id

        mock_member = MagicMock()
        mock_member.kb_id = mock_kb.id
        mock_member.user_id = uuid4()
        mock_member.role = MagicMock(value="editor")

        kb_repo = AsyncMock()
        kb_repo.find_by_id = AsyncMock(return_value=mock_kb)
        kb_repo.add_member = AsyncMock(return_value=mock_member)

        service = KBService(kb_repo)
        result = await service.add_member(mock_kb.id, owner_id, uuid4(), "editor")
        assert result["role"] == "editor"

    @pytest.mark.asyncio
    async def test_list_members_success(self):
        """测试：成功列出成员"""
        from app.services.kb_service import KBService

        mock_member = MagicMock()
        mock_member.user_id = uuid4()
        mock_member.user = MagicMock()
        mock_member.user.username = "viewer1"
        mock_member.user.display_name = "查看者"
        mock_member.role = MagicMock(value="viewer")
        mock_member.created_at = None

        kb_repo = AsyncMock()
        kb_repo.is_member = AsyncMock(return_value=True)
        kb_repo.list_members = AsyncMock(return_value=[mock_member])

        service = KBService(kb_repo)
        members = await service.list_members(uuid4(), uuid4())
        assert len(members) == 1
        assert members[0]["username"] == "viewer1"
