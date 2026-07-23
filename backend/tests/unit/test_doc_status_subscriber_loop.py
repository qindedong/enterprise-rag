"""文档状态订阅循环单元测试"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.doc_status_subscriber import doc_status_subscriber


@pytest.mark.unit
class TestDocStatusSubscriberLoop:
    """订阅主循环：消息消费、容错、优雅关闭"""

    def _pubsub_mock(self, messages: list[dict | str]):
        """构造按序吐出消息的 pubsub mock，吐完后返回 None"""
        pubsub = MagicMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()
        pubsub.aclose = AsyncMock()
        queue = list(messages)

        async def get_message(ignore_subscribe_messages=True, timeout=1.0):
            if queue:
                m = queue.pop(0)
                if isinstance(m, str):
                    return {"data": m}
                return m
            return None

        pubsub.get_message = get_message
        return pubsub

    @pytest.mark.asyncio
    async def test_consumes_messages_until_stop(self):
        """正常消费两条消息后优雅关闭"""
        pubsub = self._pubsub_mock(
            [
                {"data": json.dumps({"doc_id": str(uuid4()), "status": "processing"})},
                {
                    "data": json.dumps(
                        {"doc_id": str(uuid4()), "status": "completed", "chunk_count": 3}
                    )
                },
            ]
        )
        redis = MagicMock()
        redis.pubsub.return_value = pubsub
        redis.aclose = AsyncMock()

        stop = asyncio.Event()
        handled = []

        async def fake_handle(payload):
            handled.append(payload)
            if len(handled) == 2:
                stop.set()

        with (
            patch("redis.asyncio.from_url", return_value=redis),
            patch(
                "app.services.doc_status_subscriber.handle_status_message", side_effect=fake_handle
            ),
        ):
            await doc_status_subscriber(stop)

        assert len(handled) == 2
        pubsub.unsubscribe.assert_called_once()
        redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalid_message_skipped(self):
        """无效 JSON / 缺字段的消息被跳过不崩溃"""
        pubsub = self._pubsub_mock(
            [
                {"data": "这不是 JSON"},
                {"data": json.dumps({"wrong": "字段"})},
                {"data": json.dumps({"doc_id": "不是UUID", "status": "completed"})},
                {"data": json.dumps({"doc_id": str(uuid4()), "status": "completed"})},
            ]
        )
        redis = MagicMock()
        redis.pubsub.return_value = pubsub
        redis.aclose = AsyncMock()

        stop = asyncio.Event()
        handled = []

        async def fake_handle(payload):
            handled.append(payload)
            stop.set()

        with (
            patch("redis.asyncio.from_url", return_value=redis),
            patch(
                "app.services.doc_status_subscriber.handle_status_message", side_effect=fake_handle
            ),
        ):
            await doc_status_subscriber(stop)

        # 只有第 4 条有效消息进入 handle
        assert len(handled) == 1

    @pytest.mark.asyncio
    async def test_handler_exception_recovers(self):
        """handle 抛异常时循环继续并退避"""
        pubsub = self._pubsub_mock(
            [
                {"data": json.dumps({"doc_id": str(uuid4()), "status": "processing"})},
                {"data": json.dumps({"doc_id": str(uuid4()), "status": "completed"})},
            ]
        )
        redis = MagicMock()
        redis.pubsub.return_value = pubsub
        redis.aclose = AsyncMock()

        stop = asyncio.Event()
        calls = []

        async def flaky_handle(payload):
            calls.append(payload)
            if len(calls) == 1:
                raise RuntimeError("DB 临时故障")
            stop.set()

        async def fast_sleep(_):
            return None

        with (
            patch("redis.asyncio.from_url", return_value=redis),
            patch(
                "app.services.doc_status_subscriber.handle_status_message", side_effect=flaky_handle
            ),
            patch("app.services.doc_status_subscriber.asyncio.sleep", side_effect=fast_sleep),
        ):
            await doc_status_subscriber(stop)

        assert len(calls) == 2  # 第一条失败后，第二条仍被处理
