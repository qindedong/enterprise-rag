"""多轮对话增强单元测试：上下文裁剪 + 指代消解改写 + RAGService 历史注入"""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.rag.context_builder import format_history_for_rewrite, trim_history
from app.rag.query_rewriter import QueryRewriter
from app.services.rag_service import RAGService


def _turn(q: str, a: str) -> list[dict]:
    return [{"role": "user", "content": q}, {"role": "assistant", "content": a}]


@pytest.mark.unit
class TestTrimHistory:
    """Token 预算裁剪"""

    def test_empty(self):
        assert trim_history([]) == []
        assert trim_history(None or []) == []

    def test_short_history_kept(self):
        msgs = _turn("问题1", "回答1")
        assert trim_history(msgs) == msgs

    def test_turn_limit(self):
        """超过最大轮数时保留最近 N 轮"""
        msgs = []
        for i in range(10):
            msgs.extend(_turn(f"问题{i}", f"回答{i}"))
        trimmed = trim_history(msgs, max_turns=3)
        assert len(trimmed) == 6
        assert trimmed[0]["content"] == "问题7"
        assert trimmed[0]["role"] == "user"

    def test_token_budget(self):
        """预算不足时丢弃最早的消息"""
        msgs = []
        for i in range(5):
            msgs.extend(_turn(f"问题{i}" + "长" * 100, f"回答{i}" + "长" * 100))
        trimmed = trim_history(msgs, max_tokens=400)
        assert len(trimmed) < len(msgs)
        # 保留的应是最新的
        assert trimmed[-1]["content"].startswith("回答4")

    def test_no_orphan_assistant_start(self):
        """裁剪后首条必须是 user"""
        msgs = [*_turn("问题1", "回答1"), {"role": "assistant", "content": "孤儿回答"}]
        trimmed = trim_history(msgs, max_turns=1)
        assert trimmed == [] or trimmed[0]["role"] == "user"

    def test_invalid_roles_filtered(self):
        msgs = [
            {"role": "system", "content": "x"},
            *_turn("问", "答"),
            {"role": "user", "content": ""},
        ]
        trimmed = trim_history(msgs)
        assert all(m["role"] in ("user", "assistant") for m in trimmed)
        assert all(m["content"] for m in trimmed)


@pytest.mark.unit
class TestFormatHistory:
    def test_format(self):
        text = format_history_for_rewrite(_turn("年假几天", "5 天"))
        assert "用户: 年假几天" in text
        assert "助手: 5 天" in text


@pytest.mark.unit
class TestQueryRewriterWithHistory:
    """指代消解改写"""

    @pytest.mark.asyncio
    async def test_uses_history_template(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value={"answer": "员工年假的天数规定"})
        rewriter = QueryRewriter(llm)

        result = await rewriter.rewrite("它有几天？", history=_turn("年假是什么", "年假是带薪假期"))

        assert result == "员工年假的天数规定"
        prompt = llm.generate.call_args[0][0][0]["content"]
        assert "对话历史" in prompt
        assert "年假是什么" in prompt
        assert "它有几天？" in prompt

    @pytest.mark.asyncio
    async def test_no_history_uses_plain_template(self):
        llm = MagicMock()
        llm.generate = AsyncMock(return_value={"answer": "改写后"})
        rewriter = QueryRewriter(llm)

        await rewriter.rewrite("普通问题")

        prompt = llm.generate.call_args[0][0][0]["content"]
        assert "对话历史" not in prompt

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back(self):
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=Exception("LLM 挂了"))
        rewriter = QueryRewriter(llm)

        result = await rewriter.rewrite("原始问题", history=_turn("问", "答"))
        assert result == "原始问题"


@pytest.mark.unit
class TestRAGServiceHistory:
    """RAGService 历史注入"""

    def _make_service(self):
        retrieval = MagicMock()
        retrieval.retrieve = AsyncMock(
            return_value=[
                {"chunk_id": "c1", "document_title": "文档", "content": "内容", "score": 0.9}
            ]
        )
        llm = MagicMock()
        llm.generate = AsyncMock(
            return_value={"answer": "答案 [1]", "usage": {"total_tokens": 100}}
        )
        return RAGService(retrieval, llm), retrieval, llm

    @pytest.mark.asyncio
    async def test_history_passed_to_retrieval_and_llm(self):
        """历史应同时进入检索（指代消解）与生成消息"""
        service, retrieval, llm = self._make_service()
        history = _turn("年假是什么", "带薪假期")

        await service.ask("它有几天？", uuid4(), history=history)

        # 检索收到历史
        _, r_kwargs = retrieval.retrieve.call_args
        assert r_kwargs["history"] == history

        # 生成消息包含历史
        messages = llm.generate.call_args[0][0]
        roles = [m["role"] for m in messages]
        assert roles == ["system", "user", "assistant", "user"]
        assert messages[1]["content"] == "年假是什么"

    @pytest.mark.asyncio
    async def test_no_history_plain_messages(self):
        service, retrieval, llm = self._make_service()

        await service.ask("问题", uuid4())

        _, r_kwargs = retrieval.retrieve.call_args
        assert r_kwargs["history"] is None
        messages = llm.generate.call_args[0][0]
        assert [m["role"] for m in messages] == ["system", "user"]

    @pytest.mark.asyncio
    async def test_history_trimmed_before_use(self):
        """超长历史先裁剪再使用"""
        service, _, llm = self._make_service()
        history = []
        for i in range(20):
            history.extend(_turn(f"问题{i}" + "长" * 200, f"回答{i}" + "长" * 200))

        await service.ask("新问题", uuid4(), history=history)

        messages = llm.generate.call_args[0][0]
        # system + 裁剪后历史 + user，应远小于 40+2
        assert len(messages) < 20
