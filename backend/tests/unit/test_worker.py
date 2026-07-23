"""Worker 文档处理流程单元测试（process_document）"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.worker import _update_doc_status, process_document


def _settings():
    s = MagicMock()
    s.CHUNK_SIZE = 500
    s.CHUNK_OVERLAP = 100
    return s


def _session_factory_mock():
    """模拟 async_session 上下文管理器工厂"""
    session = AsyncMock()
    session.add = MagicMock()  # add 是同步方法，避免 coroutine 未 await 警告
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory, session


@pytest.mark.unit
class TestUpdateDocStatus:
    @pytest.mark.asyncio
    async def test_publish_payload(self):
        redis = AsyncMock()
        doc_id = uuid4()
        await _update_doc_status(redis, doc_id, "completed", chunk_count=5)

        redis.publish.assert_called_once()
        channel, payload = redis.publish.call_args[0]
        assert channel == "rag:doc_status"
        import json

        data = json.loads(payload)
        assert data["doc_id"] == str(doc_id)
        assert data["status"] == "completed"
        assert data["chunk_count"] == 5
        assert data["error_message"] is None


@pytest.mark.unit
class TestProcessDocument:
    """process_document 主流程"""

    def _make_mocks(self, tmp_path, text: str = "第一章 总则\n\n这是正文内容。" * 30):
        """创建真实文本文件 + mock 外部依赖"""
        f = tmp_path / "测试文档.md"
        f.write_text(text, encoding="utf-8")

        redis = AsyncMock()
        embedding = MagicMock()
        embedding.embed_batch = AsyncMock(side_effect=lambda chunks: [[0.1] * 512 for _ in chunks])
        qdrant = MagicMock()
        return f, redis, embedding, qdrant

    @pytest.mark.asyncio
    async def test_success_flow(self, tmp_path):
        """成功路径：解析 → 分块 → 落库 → Qdrant → completed"""
        f, redis, embedding, qdrant = self._make_mocks(tmp_path)
        factory, session = _session_factory_mock()

        with patch("app.core.database.async_session", factory):
            await process_document(
                doc_id=uuid4(),
                kb_id=uuid4(),
                file_path=str(f),
                file_ext="md",
                redis=redis,
                embedding_client=embedding,
                qdrant_store=qdrant,
                settings=_settings(),
            )

        # 分块落库
        assert session.add.call_count >= 1
        session.commit.assert_called_once()
        # 向量化 + Qdrant 写入
        embedding.embed_batch.assert_called_once()
        qdrant.upsert.assert_called_once()
        points = qdrant.upsert.call_args[0][0]
        assert len(points) == session.add.call_count
        # Qdrant 点 ID 与 chunk 落库 ID 一致
        # 状态流转：processing → completed
        statuses = [
            __import__("json").loads(call[0][1])["status"] for call in redis.publish.call_args_list
        ]
        assert statuses[0] == "processing"
        assert statuses[-1] == "completed"

    @pytest.mark.asyncio
    async def test_empty_text_marks_failed(self, tmp_path):
        """空文档 → failed"""
        f, redis, embedding, qdrant = self._make_mocks(tmp_path, text="   ")

        await process_document(
            doc_id=uuid4(),
            kb_id=uuid4(),
            file_path=str(f),
            file_ext="md",
            redis=redis,
            embedding_client=embedding,
            qdrant_store=qdrant,
            settings=_settings(),
        )

        import json

        last = json.loads(redis.publish.call_args[0][1])
        assert last["status"] == "failed"
        assert last["error_message"]
        qdrant.upsert.assert_not_called()

    @pytest.mark.asyncio
    async def test_parser_fallback_to_text_parser(self, tmp_path):
        """注册表无匹配解析器时回退 TextParser"""
        f, redis, embedding, qdrant = self._make_mocks(tmp_path)
        factory, _session = _session_factory_mock()

        with (
            patch("app.core.database.async_session", factory),
            patch(
                "app.parsers.registry.ParserRegistry.get_parser", side_effect=ValueError("不支持")
            ),
        ):
            await process_document(
                doc_id=uuid4(),
                kb_id=uuid4(),
                file_path=str(f),
                file_ext="md",
                redis=redis,
                embedding_client=embedding,
                qdrant_store=qdrant,
                settings=_settings(),
            )

        qdrant.upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_marks_failed(self, tmp_path):
        """处理异常 → failed（带错误信息）"""
        f, redis, embedding, qdrant = self._make_mocks(tmp_path)
        embedding.embed_batch = AsyncMock(side_effect=Exception("Embedding 服务炸了"))
        factory, _ = _session_factory_mock()

        with patch("app.core.database.async_session", factory):
            await process_document(
                doc_id=uuid4(),
                kb_id=uuid4(),
                file_path=str(f),
                file_ext="md",
                redis=redis,
                embedding_client=embedding,
                qdrant_store=qdrant,
                settings=_settings(),
            )

        import json

        last = json.loads(redis.publish.call_args[0][1])
        assert last["status"] == "failed"
        assert "Embedding 服务炸了" in last["error_message"]

    @pytest.mark.asyncio
    async def test_missing_file_marks_failed(self, tmp_path):
        """文件不存在 → failed"""
        redis = AsyncMock()
        embedding = MagicMock()
        embedding.embed_batch = AsyncMock(return_value=[])
        qdrant = MagicMock()

        await process_document(
            doc_id=uuid4(),
            kb_id=uuid4(),
            file_path=str(tmp_path / "不存在.md"),
            file_ext="md",
            redis=redis,
            embedding_client=embedding,
            qdrant_store=qdrant,
            settings=_settings(),
        )

        import json

        last = json.loads(redis.publish.call_args[0][1])
        assert last["status"] == "failed"
