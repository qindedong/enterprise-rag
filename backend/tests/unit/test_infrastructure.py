"""Infrastructure 与安全工具层单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import RetrievalException
from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.qdrant_client import QdrantStore


@pytest.mark.unit
class TestLLMClient:
    """LLMClient 测试"""

    @pytest.mark.asyncio
    async def test_generate_returns_answer(self):
        """测试：非流式生成返回回答"""
        from app.infrastructure.llm_client import LLMClient

        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "测试回复"
        mock_choice.finish_reason = "stop"
        mock_response.choices = [mock_choice]
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)

        with patch("app.infrastructure.llm_client.AsyncOpenAI") as mock_openai:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_instance

            client = LLMClient()
            result = await client.generate([{"role": "user", "content": "你好"}])

            assert result["answer"] == "测试回复"
            assert result["usage"]["total_tokens"] == 15

    @pytest.mark.asyncio
    async def test_generate_stream_yields_tokens(self):
        """测试：流式生成逐 token 返回"""
        from app.infrastructure.llm_client import LLMClient

        async def mock_stream():
            chunks = [
                MagicMock(choices=[MagicMock(delta=MagicMock(content="你"))]),
                MagicMock(choices=[MagicMock(delta=MagicMock(content="好"))]),
            ]
            for c in chunks:
                yield c

        with patch("app.infrastructure.llm_client.AsyncOpenAI") as mock_openai:
            mock_instance = AsyncMock()
            mock_instance.chat.completions.create = AsyncMock(return_value=mock_stream())
            mock_openai.return_value = mock_instance

            client = LLMClient()
            tokens = []
            async for token in client.generate_stream([{"role": "user", "content": "你好"}]):
                tokens.append(token)

            assert tokens == ["你", "好"]


@pytest.mark.unit
class TestEmbeddingClient:
    """EmbeddingClient 测试"""

    def test_init_with_local_model(self):
        """测试：无 API Key 时使用本地模型"""
        with patch("app.infrastructure.embedding_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                EMBEDDING_MODEL="bge-small-zh",
                EMBEDDING_API_KEY="",
                LLM_API_KEY="",
                EMBEDDING_BASE_URL="",
                LLM_BASE_URL="",
                EMBEDDING_DIMENSION=512,
                EMBEDDING_BATCH_SIZE=32,
            )

            client = EmbeddingClient()
            assert client._use_local is True

    def test_init_with_api_key_uses_remote(self):
        """测试：有 API Key 时使用远程 API"""
        with patch("app.infrastructure.embedding_client.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                EMBEDDING_MODEL="text-embedding-3-large",
                EMBEDDING_API_KEY="sk-real-openai-key-abcdef",
                LLM_API_KEY="sk-real-openai-key-abcdef",
                EMBEDDING_BASE_URL="https://api.openai.com/v1",
                LLM_BASE_URL="https://api.openai.com/v1",
                EMBEDDING_DIMENSION=3072,
                EMBEDDING_BATCH_SIZE=32,
            )

            with patch("openai.AsyncOpenAI"):
                client = EmbeddingClient()
                assert client._use_local is False

    @pytest.mark.asyncio
    async def test_embed_single(self):
        """测试：单条文本向量化"""
        mock_model = MagicMock()
        mock_model.get_sentence_embedding_dimension.return_value = 512
        mock_model.encode = MagicMock(return_value=MagicMock(tolist=lambda: [[0.1, 0.2, 0.3]]))

        with patch("app.infrastructure.embedding_client._get_local_model", return_value=mock_model):
            with patch("app.infrastructure.embedding_client.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    EMBEDDING_MODEL="bge-small-zh",
                    EMBEDDING_API_KEY="",
                    LLM_API_KEY="",
                    EMBEDDING_BASE_URL="",
                    LLM_BASE_URL="",
                    EMBEDDING_DIMENSION=512,
                    EMBEDDING_BATCH_SIZE=32,
                )

                client = EmbeddingClient()
                result = await client.embed("测试文本")
                assert len(result) == 3


@pytest.mark.unit
class TestQdrantStore:
    """QdrantStore 测试"""

    def test_init_creates_collection_if_missing(self):
        """测试：首次初始化时创建 collection"""
        mock_collection = MagicMock()
        mock_collection.collections = []

        mock_client = MagicMock()
        mock_client.get_collections = MagicMock(return_value=mock_collection)

        with patch("app.infrastructure.qdrant_client.QdrantClient", return_value=mock_client):
            with patch("app.infrastructure.qdrant_client.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    QDRANT_URL="http://localhost:6333",
                    QDRANT_COLLECTION="test_collection",
                    QDRANT_VECTOR_SIZE=512,
                )

                QdrantStore()
                assert mock_client.create_collection.called

    def test_search_returns_documents(self):
        """测试：向量检索返回结果"""
        mock_hit = MagicMock()
        mock_hit.id = "abc-123"
        mock_hit.score = 0.95
        mock_hit.payload = {
            "kb_id": "kb-1",
            "document_id": "doc-1",
            "content": "测试内容",
        }

        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(
            collections=[MagicMock(name="test_collection")]
        )
        mock_client.search.return_value = [mock_hit]

        with patch("app.infrastructure.qdrant_client.QdrantClient", return_value=mock_client):
            with patch("app.infrastructure.qdrant_client.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    QDRANT_URL="http://localhost:6333",
                    QDRANT_COLLECTION="test_collection",
                    QDRANT_VECTOR_SIZE=512,
                )

                store = QdrantStore()
                results = store.search([0.1] * 512, "kb-1", limit=10)

                assert len(results) == 1
                assert results[0]["score"] == 0.95

    def test_search_failure_raises(self):
        """测试：Qdrant 检索失败"""
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(
            collections=[MagicMock(name="test_collection")]
        )
        mock_client.search.side_effect = Exception("连接超时")

        with patch("app.infrastructure.qdrant_client.QdrantClient", return_value=mock_client):
            with patch("app.infrastructure.qdrant_client.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    QDRANT_URL="http://localhost:6333",
                    QDRANT_COLLECTION="test_collection",
                    QDRANT_VECTOR_SIZE=512,
                )

                store = QdrantStore()
                with pytest.raises(RetrievalException):
                    store.search([0.1] * 512, "kb-1")

    def test_delete_by_document(self):
        """测试：按文档 ID 删除向量"""
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(
            collections=[MagicMock(name="test_collection")]
        )

        with patch("app.infrastructure.qdrant_client.QdrantClient", return_value=mock_client):
            with patch("app.infrastructure.qdrant_client.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    QDRANT_URL="http://localhost:6333",
                    QDRANT_COLLECTION="test_collection",
                    QDRANT_VECTOR_SIZE=512,
                )

                store = QdrantStore()
                store.delete_by_document("doc-123")
                assert mock_client.delete.called

    def test_delete_by_kb(self):
        """测试：按知识库 ID 删除向量"""
        mock_client = MagicMock()
        mock_client.get_collections.return_value = MagicMock(
            collections=[MagicMock(name="test_collection")]
        )

        with patch("app.infrastructure.qdrant_client.QdrantClient", return_value=mock_client):
            with patch("app.infrastructure.qdrant_client.get_settings") as mock_settings:
                mock_settings.return_value = MagicMock(
                    QDRANT_URL="http://localhost:6333",
                    QDRANT_COLLECTION="test_collection",
                    QDRANT_VECTOR_SIZE=512,
                )

                store = QdrantStore()
                store.delete_by_kb("kb-123")
                assert mock_client.delete.called


@pytest.mark.unit
class TestSecurityUtils:
    """安全工具测试"""

    def test_hash_and_verify_password(self):
        """测试：密码哈希和验证"""
        from app.utils.security import hash_password, verify_password

        hashed = hash_password("MySecureP@ss123")
        assert hashed != "MySecureP@ss123"
        assert verify_password("MySecureP@ss123", hashed)
        assert not verify_password("WrongPassword", hashed)

    def test_jwt_create_and_decode(self):
        """测试：JWT Token 创建和解码"""
        from app.utils.security import create_access_token, decode_token

        token = create_access_token("user-123", "user")
        payload = decode_token(token)

        assert payload["sub"] == "user-123"
        assert payload["role"] == "user"
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        """测试：Refresh Token 类型标记"""
        from app.utils.security import create_refresh_token, decode_token

        token = create_refresh_token("user-456")
        payload = decode_token(token)

        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"


@pytest.mark.unit
class TestResponseModels:
    """响应模型测试"""

    def test_api_response(self):
        """测试：APIResponse 构造"""
        from app.models.request_response.response import APIResponse

        resp = APIResponse(data={"key": "value"})
        assert resp.code == 200
        assert resp.message == "success"
        assert resp.data == {"key": "value"}

    def test_api_response_error(self):
        """测试：APIResponse 错误格式"""
        from app.models.request_response.response import APIResponse

        resp = APIResponse(code=404, message="未找到", data=None)
        assert resp.code == 404
        assert resp.message == "未找到"

    def test_paginated_response(self):
        """测试：PaginatedResponse"""
        from app.models.request_response.response import (
            PageInfo,
            PaginatedData,
            PaginatedResponse,
        )

        page_info = PageInfo(total=100, page=1, page_size=20)
        paged_data = PaginatedData(items=[{"a": 1}], page_info=page_info)
        resp = PaginatedResponse(data=paged_data)

        assert resp.code == 200
        assert resp.data.items == [{"a": 1}]
        assert resp.data.page_info.total == 100
