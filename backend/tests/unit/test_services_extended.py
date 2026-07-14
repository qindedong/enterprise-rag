"""Service 层扩展测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.document_service import DocumentService, ALLOWED_MIME_TYPES
from app.services.rag_service import RAGService
from app.services.conversation_service import ConversationService
from app.core.exceptions import NotFoundException, DuplicateException, ValidationException


@pytest.mark.unit
class TestDocumentService:
    """DocumentService 补充测试"""

    @pytest.mark.asyncio
    async def test_upload_validates_file_type(self):
        """测试：不支持的文件类型抛出异常"""
        service = DocumentService(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())

        with pytest.raises(ValidationException):
            await service.upload_document(
                uuid4(), "test.exe", "application/x-msdownload", b"fake"
            )

    @pytest.mark.asyncio
    async def test_get_detail_not_found(self):
        """测试：获取不存在的文档详情"""
        mock_doc_repo = AsyncMock()
        mock_doc_repo.find_by_id = AsyncMock(return_value=None)

        service = DocumentService(mock_doc_repo, AsyncMock(), AsyncMock(), AsyncMock())
        with pytest.raises(NotFoundException):
            await service.get_detail(uuid4())

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self):
        """测试：删除不存在的文档"""
        mock_doc_repo = AsyncMock()
        mock_doc_repo.find_by_id = AsyncMock(return_value=None)

        service = DocumentService(mock_doc_repo, AsyncMock(), AsyncMock(), AsyncMock())
        with pytest.raises(NotFoundException):
            await service.delete_document(uuid4())

    @pytest.mark.asyncio
    async def test_list_documents_returns_tuple(self):
        """测试：文档列表返回 (items, total) 元组"""
        mock_doc_repo = AsyncMock()
        mock_doc_repo.list_by_kb = AsyncMock(return_value=([], 0))

        service = DocumentService(mock_doc_repo, AsyncMock(), AsyncMock(), AsyncMock())
        items, total = await service.list_documents(uuid4())
        assert isinstance(items, list)
        assert total == 0

    @pytest.mark.asyncio
    async def test_reprocess_only_failed(self):
        """测试：只能重新处理失败的文档"""
        mock_doc = AsyncMock()
        mock_doc.status = MagicMock(value="completed")

        mock_doc_repo = AsyncMock()
        mock_doc_repo.find_by_id = AsyncMock(return_value=mock_doc)

        service = DocumentService(mock_doc_repo, AsyncMock(), AsyncMock(), AsyncMock())
        with pytest.raises(ValidationException):
            await service.reprocess(uuid4())

    def test_allowed_mime_types(self):
        """测试：MIME 类型映射正确"""
        assert "application/pdf" in ALLOWED_MIME_TYPES
        assert "text/markdown" in ALLOWED_MIME_TYPES
        assert "text/plain" in ALLOWED_MIME_TYPES
        assert ALLOWED_MIME_TYPES["application/pdf"] == "pdf"

    @pytest.mark.asyncio
    async def test_to_response_handles_none_values(self):
        """测试：_to_response 处理 None 字段"""
        mock_doc = MagicMock()
        mock_doc.id = uuid4()
        mock_doc.kb_id = uuid4()
        mock_doc.title = "测试"
        mock_doc.file_type = None
        mock_doc.file_size = None
        mock_doc.status = None
        mock_doc.chunk_count = 0
        mock_doc.error_message = None
        mock_doc.created_at = None
        mock_doc.updated_at = None

        service = DocumentService(AsyncMock(), AsyncMock(), AsyncMock(), AsyncMock())
        result = service._to_response(mock_doc)
        assert result["title"] == "测试"
        assert result["file_type"] is None


@pytest.mark.unit
class TestRAGService:
    """RAGService 补充测试"""

    @pytest.mark.asyncio
    async def test_ask_returns_no_answer_when_empty_docs(self):
        """测试：检索结果为空时返回兜底回答"""
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(return_value=[])

        mock_llm = AsyncMock()

        service = RAGService(mock_retrieval, mock_llm)
        result = await service.ask("问题", uuid4())

        assert "无法回答" in result["answer"]
        assert result["citations"] == []

    @pytest.mark.asyncio
    async def test_ask_generates_answer_with_citations(self):
        """测试：正常路径生成回答和引用"""
        mock_retrieval = AsyncMock()
        mock_retrieval.retrieve = AsyncMock(return_value=[
            {
                "document_title": "手册.md",
                "content": "公司年假是15天。",
                "chunk_id": str(uuid4()),
                "score": 0.95,
                "title": "手册.md",
            }
        ])

        mock_llm = AsyncMock()
        mock_llm.generate = AsyncMock(return_value={
            "answer": "年假共有15天 [1]。",
            "usage": {"total_tokens": 100},
        })

        service = RAGService(mock_retrieval, mock_llm)
        result = await service.ask("年假有多少天？", uuid4())

        assert "15天" in result["answer"]
        assert len(result["citations"]) > 0
        assert "processing_time_ms" in result


@pytest.mark.unit
class TestConversationService:
    """ConversationService 补充测试"""

    @pytest.mark.asyncio
    async def test_create_or_get_creates_new(self):
        """测试：无活跃对话时创建新的"""
        mock_conv_repo = AsyncMock()
        mock_conv_repo.list_by_user = AsyncMock(return_value=([], 0))
        mock_conv = AsyncMock()
        mock_conv.id = uuid4()
        mock_conv.kb_id = uuid4()
        mock_conv.title = "测试标题"
        mock_conv.message_count = 0
        mock_conv.status = MagicMock(value="active")
        mock_conv.created_at = None
        mock_conv.updated_at = None
        mock_conv_repo.create = AsyncMock(return_value=mock_conv)

        service = ConversationService(mock_conv_repo, AsyncMock())
        result = await service.create_or_get(uuid4(), uuid4(), "这是第一个问题？")

        assert mock_conv_repo.create.called
        assert result["title"] == "测试标题"

    @pytest.mark.asyncio
    async def test_get_messages_not_found(self):
        """测试：获取不存在的对话消息"""
        mock_conv_repo = AsyncMock()
        mock_conv_repo.find_by_id = AsyncMock(return_value=None)

        service = ConversationService(mock_conv_repo, AsyncMock())
        with pytest.raises(NotFoundException):
            await service.get_messages(uuid4())

    @pytest.mark.asyncio
    async def test_add_message(self):
        """测试：添加消息到对话"""
        mock_conv_repo = AsyncMock()
        mock_conv_repo.update_message_count = AsyncMock()

        mock_msg = AsyncMock()
        mock_msg.id = uuid4()
        mock_msg.role = MagicMock(value="user")
        mock_msg.content = "测试消息"
        mock_msg.created_at = None

        mock_msg_repo = AsyncMock()
        mock_msg_repo.create = AsyncMock(return_value=mock_msg)

        service = ConversationService(mock_conv_repo, mock_msg_repo)
        result = await service.add_message(uuid4(), "user", "测试消息")

        assert result["content"] == "测试消息"
        assert mock_msg_repo.create.called

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self):
        """测试：删除不存在的对话"""
        mock_conv_repo = AsyncMock()
        mock_conv_repo.find_by_id = AsyncMock(return_value=None)

        service = ConversationService(mock_conv_repo, AsyncMock())
        with pytest.raises(NotFoundException):
            await service.delete(uuid4())


@pytest.mark.unit
class TestAuthService:
    """AuthService 补充测试"""

    @pytest.mark.asyncio
    @patch("app.services.auth_service.hash_password")
    async def test_register_short_password(self, mock_hash):
        """测试：密码太短抛出异常"""
        mock_hash.return_value = "hashed"
        user_repo = AsyncMock()
        user_repo.find_by_username.return_value = None
        user_repo.find_by_email.return_value = None

        service = __import__("app.services.auth_service", fromlist=["AuthService"]).AuthService(user_repo)
        with pytest.raises(ValidationException):
            await service.register("user", "user@test.com", "short")

    @pytest.mark.asyncio
    async def test_login_inactive_user(self):
        """测试：已禁用用户登录失败"""
        mock_user = AsyncMock()
        mock_user.is_active = False
        mock_user.hashed_password = "hashed"

        user_repo = AsyncMock()
        user_repo.find_by_email = AsyncMock(return_value=mock_user)

        with patch("app.services.auth_service.verify_password", return_value=True):
            from app.core.exceptions import UnauthorizedException
            from app.services.auth_service import AuthService

            service = AuthService(user_repo)
            with pytest.raises(UnauthorizedException):
                await service.login("inactive@test.com", "password")
