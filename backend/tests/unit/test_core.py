"""核心模块单元测试"""

import pytest

from app.core.config import get_settings, Settings
from app.core.exceptions import (
    AppException,
    NotFoundException,
    ValidationException,
    DuplicateException,
    UnauthorizedException,
    ForbiddenException,
    LLMException,
    RetrievalException,
)


class TestSettings:
    """配置模块测试"""

    def test_get_settings_returns_singleton(self):
        """测试：get_settings 返回单例"""
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_default_values(self):
        """测试：默认值正确"""
        settings = Settings()
        assert settings.APP_NAME == "企业知识库RAG"
        assert settings.CHUNK_SIZE == 500
        assert settings.CHUNK_OVERLAP == 100


class TestExceptions:
    """异常体系测试"""

    def test_app_exception_base(self):
        """测试：AppException 基类"""
        exc = AppException(400, "参数错误", "name 不能为空")
        assert exc.code == 400
        assert exc.message == "参数错误"
        assert exc.detail == "name 不能为空"

    def test_not_found_exception(self):
        """测试：NotFoundException"""
        exc = NotFoundException("知识库", "kb-123")
        assert exc.code == 404
        assert "知识库" in exc.message

    def test_validation_exception(self):
        """测试：ValidationException"""
        exc = ValidationException("分块大小超出范围")
        assert exc.code == 422

    def test_duplicate_exception(self):
        """测试：DuplicateException"""
        exc = DuplicateException("用户名", "username=admin")
        assert exc.code == 409

    def test_unauthorized_exception(self):
        """测试：UnauthorizedException"""
        exc = UnauthorizedException()
        assert exc.code == 401

    def test_forbidden_exception(self):
        """测试：ForbiddenException"""
        exc = ForbiddenException("只有管理员可以执行此操作")
        assert exc.code == 403

    def test_llm_exception(self):
        """测试：LLMException"""
        exc = LLMException("API Key 无效")
        assert exc.code == 502

    def test_retrieval_exception(self):
        """测试：RetrievalException"""
        exc = RetrievalException("Qdrant 连接超时")
        assert exc.code == 500

    def test_all_exceptions_inherit_from_app(self):
        """测试：所有异常都继承自 AppException"""
        exceptions = [
            NotFoundException("test"),
            ValidationException("test"),
            DuplicateException("test"),
            UnauthorizedException(),
            ForbiddenException(),
            LLMException(),
            RetrievalException(),
        ]
        for exc in exceptions:
            assert isinstance(exc, AppException)
