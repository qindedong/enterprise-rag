"""
Qdrant 向量数据库客户端

封装 Qdrant 客户端的常用操作：创建集合、插入向量、搜索、删除.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

from app.core.config import get_settings
from app.core.exceptions import RetrievalException
from app.core.logger import get_logger

logger = get_logger(__name__)


class QdrantStore:
    """Qdrant 向量存储封装"""

    def __init__(self):
        settings = get_settings()
        self._client = QdrantClient(url=settings.QDRANT_URL)
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.QDRANT_VECTOR_SIZE
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """确保 Collection 存在，不存在则创建"""
        collections = [c.name for c in self._client.get_collections().collections]
        if self.collection_name not in collections:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Qdrant Collection 已创建: {self.collection_name}")

            # 创建 Payload 索引（加速按 kb_id 过滤）
            for field in ["kb_id", "document_id"]:
                self._client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword",
                )

    def upsert(self, points: list[PointStruct]) -> None:
        """批量插入或更新向量点"""
        try:
            self._client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            logger.info(f"Qdrant 写入完成: {len(points)} 个点")
        except Exception as e:
            raise RetrievalException(f"向量写入失败: {e}")

    def search(
        self,
        query_vector: list[float],
        kb_id: str,
        limit: int = 50,
    ) -> list[dict]:
        """
        向量检索

        Args:
            query_vector: 查询向量
            kb_id: 知识库 ID（用于过滤）
            limit: 返回数量（默认 50）

        Returns:
            匹配的 Point 列表（含 payload 和 score）
        """
        try:
            results = self._client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=Filter(
                    must=[FieldCondition(key="kb_id", match=MatchValue(value=kb_id))]
                ),
                limit=limit,
                with_payload=True,
            )
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    **hit.payload,
                }
                for hit in results
            ]
        except Exception as e:
            raise RetrievalException(f"向量检索失败: {e}")

    def delete_by_document(self, document_id: str) -> None:
        """删除指定文档的所有向量"""
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
                wait=True,
            )
            logger.info(f"Qdrant 向量已删除: document_id={document_id}")
        except Exception as e:
            logger.error(f"删除向量失败: {e}")

    def delete_by_kb(self, kb_id: str) -> None:
        """删除指定知识库的所有向量"""
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[FieldCondition(key="kb_id", match=MatchValue(value=kb_id))]
                ),
                wait=True,
            )
            logger.info(f"Qdrant 向量已删除: kb_id={kb_id}")
        except Exception as e:
            logger.error(f"删除向量失败: {e}")
