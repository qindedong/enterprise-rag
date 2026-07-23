"""文档状态订阅者单元测试"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.database.document import DocStatus
from app.services.doc_status_subscriber import handle_status_message


@pytest.mark.unit
class TestHandleStatusMessage:
    """handle_status_message 落库逻辑"""

    @pytest.mark.asyncio
    @patch("app.services.doc_status_subscriber.async_session")
    @patch("app.services.doc_status_subscriber.DocumentRepository")
    async def test_completed_with_chunk_count(self, mock_repo_class, mock_session_factory):
        """测试：completed 状态 + chunk_count 正确落库并提交"""
        session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        mock_repo_class.return_value = repo

        doc_id = uuid4()
        await handle_status_message(
            {"doc_id": str(doc_id), "status": "completed", "chunk_count": 15, "error_message": None}
        )

        repo.update_status.assert_called_once_with(doc_id, DocStatus.COMPLETED, chunk_count=15)
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.doc_status_subscriber.async_session")
    @patch("app.services.doc_status_subscriber.DocumentRepository")
    async def test_failed_with_error_message(self, mock_repo_class, mock_session_factory):
        """测试：failed 状态携带错误信息"""
        session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        mock_repo_class.return_value = repo

        doc_id = uuid4()
        await handle_status_message(
            {
                "doc_id": str(doc_id),
                "status": "failed",
                "chunk_count": 0,
                "error_message": "未能提取到文字内容",
            }
        )

        repo.update_status.assert_called_once_with(
            doc_id, DocStatus.FAILED, error_message="未能提取到文字内容"
        )

    @pytest.mark.asyncio
    @patch("app.services.doc_status_subscriber.async_session")
    @patch("app.services.doc_status_subscriber.DocumentRepository")
    async def test_processing_no_extra_fields(self, mock_repo_class, mock_session_factory):
        """测试：processing 状态不带额外字段"""
        session = AsyncMock()
        mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = AsyncMock()
        mock_repo_class.return_value = repo

        doc_id = uuid4()
        await handle_status_message(
            {"doc_id": str(doc_id), "status": "processing", "chunk_count": 0, "error_message": None}
        )

        repo.update_status.assert_called_once_with(doc_id, DocStatus.PROCESSING)
