"""
Worker — 文档异步处理服务

从 Redis 队列（BRPOP）获取文档处理任务，在后台执行解析→分块→向量化流程。
支持优雅关闭和多 Worker 并发。

启动方式:
    python -m app.worker

依赖 Redis 作为消息队列。
"""

import asyncio
import contextlib
import json
import os
import signal
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from qdrant_client.models import PointStruct

if TYPE_CHECKING:
    from app.infrastructure.embedding_client import EmbeddingClient
    from app.infrastructure.qdrant_client import QdrantStore

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def main():
    """Worker 主循环"""
    # 延迟导入，确保日志和配置先就绪
    import redis.asyncio as aioredis
    from redis.exceptions import TimeoutError as RedisTimeoutError

    from app.core.config import get_settings
    from app.infrastructure.embedding_client import EmbeddingClient
    from app.infrastructure.qdrant_client import QdrantStore

    settings = get_settings()

    # 日志
    import logging

    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-8s | worker | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger = logging.getLogger("worker")

    logger.info(f"🚀 Worker 启动中... (环境: {settings.APP_NAME})")

    # Redis 连接
    redis_url = settings.REDIS_URL
    redis = aioredis.from_url(redis_url, decode_responses=True)
    logger.info(f"已连接 Redis: {redis_url}")

    # AI 服务
    embedding_client = EmbeddingClient()
    qdrant_store = QdrantStore()

    # 队列名称
    queue_key = "rag:doc_process_queue"

    # 优雅关闭
    shutdown_flag = asyncio.Event()

    def handle_signal(sig):
        logger.info(f"收到信号 {sig.name}，正在优雅关闭...")
        shutdown_flag.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(Exception):
            signal.signal(sig, handle_signal)

    logger.info(f"开始监听队列: {queue_key}")

    processed = 0
    while not shutdown_flag.is_set():
        try:
            # BRPOP 阻塞等待任务（超时 5 秒以允许检查 shutdown_flag）
            result = await asyncio.wait_for(
                redis.brpop(queue_key, timeout=5),
                timeout=6,
            )

            if result is None:
                continue

            _, task_json = result
            task = json.loads(task_json)
            doc_id = task["doc_id"]
            kb_id = task["kb_id"]
            file_path = task["file_path"]
            file_ext = task["file_type"]

            logger.info(f"📄 收到任务: doc={doc_id} kb={kb_id}")

            # 处理文档
            await process_document(
                doc_id=UUID(doc_id),
                kb_id=UUID(kb_id),
                file_path=file_path,
                file_ext=file_ext,
                redis=redis,
                embedding_client=embedding_client,
                qdrant_store=qdrant_store,
                settings=settings,
            )

            processed += 1
            logger.info(f"✅ 已完成 {processed} 个任务")

        except (TimeoutError, RedisTimeoutError):
            # asyncio.wait_for 超时（内置 TimeoutError）或
            # redis.asyncio 阻塞读超时（redis.exceptions.TimeoutError，不继承内置类）
            continue
        except Exception as e:
            logger.error(f"Worker 异常: {e}", exc_info=True)
            await asyncio.sleep(1)

    await redis.aclose()
    logger.info(f"Worker 已关闭，共处理 {processed} 个任务")


async def process_document(
    doc_id: UUID,
    kb_id: UUID,
    file_path: str,
    file_ext: str,
    redis,
    embedding_client: "EmbeddingClient",
    qdrant_store: "QdrantStore",
    settings,
) -> None:
    """处理文档：解析 → 分块 → 向量化 → Qdrant"""

    import logging

    logger = logging.getLogger("worker")

    # 获取文档标题——从文件名推导
    import os

    from app.parsers.registry import ParserRegistry
    from app.utils.text_splitter import TextSplitter

    doc_title = os.path.basename(file_path) if file_path else "未知文档"

    # 更新状态为处理中
    await _update_doc_status(redis, doc_id, "processing")

    try:
        # Step 1: 解析
        logger.info(f"📖 解析文档: {doc_id}")
        mime = f"application/{file_ext}" if file_ext == "pdf" else f"text/{file_ext}"
        try:
            parser = ParserRegistry.get_parser(mime)
            raw_text = parser.parse(file_path)
        except Exception:
            from app.parsers.text_parser import TextParser

            raw_text = TextParser().parse(file_path)

        if not raw_text or not raw_text.strip():
            await _update_doc_status(redis, doc_id, "failed", error="未能提取到文字内容")
            return

        # Step 2: 分块
        splitter = TextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        split_result = splitter.split(raw_text)
        if split_result.total_chunks == 0:
            await _update_doc_status(redis, doc_id, "failed", error="分块结果为空")
            return

        # Step 3: 向量化
        embeddings = await embedding_client.embed_batch(split_result.chunks)

        # Step 4: 落库 document_chunks（jieba 预分词，供 BM25 全文检索）
        import jieba

        from app.core.database import async_session
        from app.models.database.document import DocumentChunk

        chunk_ids: list[str] = []
        async with async_session() as session:
            for i, chunk_text in enumerate(split_result.chunks):
                chunk = DocumentChunk(
                    document_id=doc_id,
                    kb_id=kb_id,
                    chunk_index=i,
                    content=chunk_text,
                    content_segmented=" ".join(jieba.cut(chunk_text)),
                )
                session.add(chunk)
                await session.flush()  # 生成 chunk.id
                chunk_ids.append(str(chunk.id))
            await session.commit()
        logger.info(f"分块落库完成: {len(chunk_ids)} 条 → document_chunks")

        # Step 5: 写入 Qdrant（点 ID 与 document_chunks.id 一致，便于混合检索对齐）
        points = []
        for i, (chunk_text, embedding) in enumerate(
            zip(split_result.chunks, embeddings, strict=False)
        ):
            point = PointStruct(
                id=chunk_ids[i],
                vector=embedding,
                payload={
                    "kb_id": str(kb_id),
                    "document_id": str(doc_id),
                    "document_title": doc_title,
                    "chunk_id": chunk_ids[i],
                    "chunk_index": i,
                    "content": chunk_text[:2000],
                    "created_at": datetime.now(UTC).isoformat(),
                },
            )
            points.append(point)

        qdrant_store.upsert(points)

        # Step 6: 标记完成
        await _update_doc_status(
            redis,
            doc_id,
            "completed",
            chunk_count=split_result.total_chunks,
        )
        logger.info(f"✅ 文档处理完成: {doc_id}, {split_result.total_chunks} 个分块")

    except Exception as e:
        logger.error(f"文档处理失败: {doc_id}: {e}", exc_info=True)
        await _update_doc_status(redis, doc_id, "failed", error=str(e)[:500])


async def _update_doc_status(
    redis,
    doc_id: UUID,
    status: str,
    error: str | None = None,
    chunk_count: int = 0,
) -> None:
    """通过 Redis pub/sub 通知 API 端更新文档状态"""
    payload = {
        "doc_id": str(doc_id),
        "status": status,
        "chunk_count": chunk_count,
        "error_message": error,
    }
    await redis.publish("rag:doc_status", json.dumps(payload))


if __name__ == "__main__":
    asyncio.run(main())
