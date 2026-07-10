"""Prompt 模板与查询改写单元测试"""

import pytest
from unittest.mock import AsyncMock

from app.prompts.registry import PromptRegistry, PromptTemplate
from app.rag.query_rewriter import QueryRewriter


class TestPromptRegistry:
    """Prompt 模板注册中心测试"""

    def test_get_registered_template(self):
        """测试：获取已注册的模板"""
        tmpl = PromptRegistry.get("rag_system")
        assert tmpl is not None
        assert "严谨" in tmpl.template
        assert "引用" in tmpl.template

    def test_get_nonexistent_raises(self):
        """测试：获取不存在的模板抛出 ValueError"""
        with pytest.raises(ValueError, match="不存在"):
            PromptRegistry.get("nonexistent_template")

    def test_render_with_valid_vars(self):
        """测试：正确渲染模板"""
        result = PromptRegistry.render(
            "rag_user",
            context="测试上下文",
            question="测试问题",
        )
        assert "测试上下文" in result
        assert "测试问题" in result
        assert "参考资料" in result

    def test_render_with_missing_vars_raises(self):
        """测试：缺少变量抛出 ValueError"""
        with pytest.raises(ValueError, match="缺少"):
            PromptRegistry.render("rag_user", context="only context")

    def test_register_new_template(self):
        """测试：注册新模板"""
        tmpl = PromptTemplate(
            name="test_registry_template",
            template="Hello {username}",
            variables=["username"],
            description="测试模板",
        )
        PromptRegistry.register(tmpl)
        result = PromptRegistry.render("test_registry_template", username="World")
        assert result == "Hello World"


class TestQueryRewriter:
    """查询改写器测试"""

    @pytest.mark.asyncio
    async def test_rewrite_short_question_returns_original(self):
        """测试：短问题直接返回原文"""
        llm_client = AsyncMock()
        rewriter = QueryRewriter(llm_client)

        # 太短的问题不改写
        result = await rewriter.rewrite("ab")
        assert result == "ab"

    @pytest.mark.asyncio
    async def test_rewrite_returns_original_on_failure(self):
        """测试：LLM 调用失败时返回原文"""
        llm_client = AsyncMock()
        llm_client.generate.side_effect = Exception("API 超时")

        rewriter = QueryRewriter(llm_client)
        result = await rewriter.rewrite("公司年假有多少天？")

        assert result == "公司年假有多少天？"
