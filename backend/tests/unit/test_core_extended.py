"""Core 层补充测试 — Logger, ExceptionHandlers, Exceptions"""

import pytest
import logging
from unittest.mock import MagicMock

from app.core.logger import StructuredFormatter
from app.core.exceptions import (
    NotFoundException, EmbeddingException, ProcessingException, AppException,
    ValidationException, DuplicateException, UnauthorizedException,
    ForbiddenException, LLMException, RetrievalException,
)
from app.core.exception_handlers import app_exception_handler, global_exception_handler


class TestStructuredFormatter:
    """StructuredFormatter 测试"""

    def test_format_with_extra_fields(self):
        """测试：带 extra_fields 的日志格式化"""
        formatter = StructuredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        record = logging.LogRecord(
            name="test_logger", level=logging.INFO,
            pathname="test.py", lineno=10,
            msg="文档处理完成", args=(),
            exc_info=None,
        )
        record.extra_fields = {"doc_id": "abc123", "chunks": 15}

        result = formatter.format(record)
        assert "文档处理完成" in result
        assert "doc_id" in result
        assert "abc123" in result

    def test_format_with_exception(self):
        """测试：带异常堆栈的日志格式化"""
        formatter = StructuredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        try:
            raise ValueError("测试异常")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="test_logger", level=logging.ERROR,
                pathname="test.py", lineno=20,
                msg="操作失败", args=(),
                exc_info=sys.exc_info(),
            )

        result = formatter.format(record)
        assert "操作失败" in result
        assert "exception" in result
        assert "ValueError" in result


class TestExceptionHandlers:
    """异常处理器测试"""

    @pytest.mark.asyncio
    async def test_app_exception_handler(self):
        """测试：AppException 处理返回正确 JSON"""
        from fastapi import Request
        from starlette.datastructures import MutableHeaders

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)

        exc = NotFoundException("资源", "id-1")
        response = await app_exception_handler(request, exc)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_global_exception_handler(self):
        """测试：未处理异常返回 500"""
        from fastapi import Request

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/broken",
            "headers": [],
            "query_string": b"",
        }
        request = Request(scope)

        response = await global_exception_handler(request, ValueError("崩溃"))

        assert response.status_code == 500
        body = response.body.decode("utf-8")
        assert "服务器内部错误" in body


class TestExceptionsEdgeCases:
    """异常边角情况测试"""

    def test_not_found_without_resource(self):
        """测试：resource=None 时的 NotFoundException"""
        exc = NotFoundException(identifier="some-id")
        assert exc.code == 404
        assert exc.message == "资源不存在"

    def test_embedding_exception(self):
        """测试：EmbeddingException 构造"""
        exc = EmbeddingException("向量化超时")
        assert exc.code == 502
        assert "Embedding" in exc.message

    def test_processing_exception(self):
        """测试：ProcessingException 构造"""
        exc = ProcessingException("分块失败")
        assert exc.code == 500
        assert "文档处理失败" in exc.message

    def test_all_exceptions_inherit_from_app(self):
        """测试：所有 8 种异常都继承 AppException"""
        exceptions = [
            NotFoundException("t"),
            ValidationException("t"),
            DuplicateException("t"),
            UnauthorizedException(),
            ForbiddenException(),
            LLMException(),
            RetrievalException(),
            EmbeddingException(),
            ProcessingException(),
        ]
        for exc in exceptions:
            assert isinstance(exc, AppException), f"{type(exc).__name__} 未继承 AppException"


class TestRequestIDMiddleware:
    """Request ID 中间件测试"""

    @pytest.mark.asyncio
    async def test_middleware_sets_request_id(self, client, override_get_db):
        """测试：响应头包含 X-Request-ID"""
        response = await client.get("/health")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0
