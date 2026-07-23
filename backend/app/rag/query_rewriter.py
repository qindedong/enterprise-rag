"""
查询改写器

使用 LLM 将用户口语化查询改写为更适合检索的形式.
"""

from app.core.logger import get_logger
from app.infrastructure.llm_client import LLMClient
from app.prompts.registry import PromptRegistry

logger = get_logger(__name__)


class QueryRewriter:
    """查询改写器 — 基于 LLM"""

    def __init__(self, llm_client: LLMClient):
        self.llm_client = llm_client

    async def rewrite(self, question: str, history: list[dict] | None = None) -> str:
        """
        改写用户查询

        Args:
            question: 用户原始问题
            history: 对话历史（可选，提供时做指代消解与上下文补全）

        Returns:
            改写后的查询语句（如果改写失败则返回原文）
        """
        if not question or len(question) < 3:
            return question

        try:
            if history:
                from app.rag.context_builder import format_history_for_rewrite

                prompt = PromptRegistry.render(
                    "query_rewrite_with_history",
                    history=format_history_for_rewrite(history),
                    question=question,
                )
            else:
                prompt = PromptRegistry.render("query_rewrite", question=question)

            result = await self.llm_client.generate([{"role": "user", "content": prompt}])
            rewritten = result["answer"].strip()
            if rewritten and rewritten != question:
                logger.info(f"查询改写: '{question[:50]}...' → '{rewritten[:50]}...'")
                return rewritten
        except Exception as e:
            logger.warning(f"查询改写失败，使用原文: {e}")

        return question
