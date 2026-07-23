"""
文档状态订阅者

Worker 处理完文档后通过 Redis pub/sub（rag:doc_status）发布状态变更，
本模块在 API 进程中以后台任务订阅该频道并将状态落库（documents 表）。

消息格式:
    {"doc_id": "...", "status": "processing|completed|failed",
     "chunk_count": 12, "error_message": null}
"""

import asyncio
import json
from uuid import UUID

from app.core.config import get_settings
from app.core.database import async_session
from app.core.logger import get_logger
from app.models.database.document import DocStatus
from app.repositories.document_repository import DocumentRepository

logger = get_logger(__name__)

CHANNEL = "rag:doc_status"


async def handle_status_message(payload: dict) -> None:
    """处理单条状态消息：更新 documents 表"""
    doc_id = UUID(payload["doc_id"])
    status = DocStatus(payload["status"])
    updates: dict = {}
    if payload.get("chunk_count"):
        updates["chunk_count"] = payload["chunk_count"]
    if payload.get("error_message"):
        updates["error_message"] = payload["error_message"]

    async with async_session() as session:
        repo = DocumentRepository(session)
        await repo.update_status(doc_id, status, **updates)
        await session.commit()

    logger.info(f"文档状态已更新: {doc_id} → {status.value}")


async def doc_status_subscriber(stop_event: asyncio.Event) -> None:
    """订阅循环 — 作为 lifespan 后台任务运行"""
    import redis.asyncio as aioredis

    settings = get_settings()
    redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(CHANNEL)
    logger.info(f"已订阅文档状态频道: {CHANNEL}")

    try:
        while not stop_event.is_set():
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                payload = json.loads(message["data"])
                await handle_status_message(payload)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"无效的文档状态消息: {e}")
            except Exception as e:
                logger.error(f"文档状态订阅处理异常: {e}", exc_info=True)
                await asyncio.sleep(1)
    finally:
        await pubsub.unsubscribe(CHANNEL)
        await pubsub.aclose()
        await redis.aclose()
        logger.info("文档状态订阅已关闭")
