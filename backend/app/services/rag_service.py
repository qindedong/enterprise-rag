"""
RAG 服务

负责完整 RAG 流程编排：检索 → Prompt 组装 → LLM 生成 → 引用提取.
"""

import re
import time
from uuid import UUID

from app.core.logger import get_logger
from app.infrastructure.llm_client import LLMClient
from app.prompts.registry import PromptRegistry
from app.rag.pipeline import RetrievalPipeline

logger = get_logger(__name__)


class RAGService:
    """RAG 问答服务"""

    def __init__(
        self,
        retrieval_pipeline: RetrievalPipeline,
        llm_client: LLMClient,
    ):
        self.retrieval = retrieval_pipeline
        self.llm_client = llm_client

    async def ask(self, question: str, kb_id: UUID) -> dict:
        """
        RAG 问答（非流式）

        Returns:
            包含 answer, citations, token_usage, processing_time_ms 的字典
        """
        start = time.time()

        # Step 1: 检索
        docs = await self.retrieval.retrieve(question, kb_id)
        if not docs:
            return {
                "answer": "根据现有资料，无法回答这个问题。建议：1) 换个方式提问 2) 检查知识库是否有相关文档",
                "citations": [],
                "token_usage": {},
                "processing_time_ms": (time.time() - start) * 1000,
            }

        # Step 2: 组装 Context（编号 + 文档名 + 内容）
        context_parts = []
        citations = []
        for i, doc in enumerate(docs):
            idx = i + 1
            title = doc.get("document_title", doc.get("title", "未知文档"))
            content = doc.get("content", "")
            context_parts.append(f"[{idx}] {title}\n{content}")

            citations.append({
                "index": idx,
                "document_title": title,
                "chunk_id": doc.get("chunk_id", ""),
                "content_snippet": content[:200] if content else "",
                "relevance_score": doc.get("score", 0),
            })

        context = "\n\n---\n\n".join(context_parts)

        # Step 3: 组装 Prompt
        system_prompt = PromptRegistry.render("rag_system")
        user_prompt = PromptRegistry.render("rag_user", context=context, question=question)

        # Step 4: LLM 生成
        result = await self.llm_client.generate([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        # Step 5: 校验引用
        answer = result["answer"]
        cited_nums = set(int(n) for n in re.findall(r"\[(\d+)\]", answer))
        valid_citations = [c for c in citations if c["index"] in cited_nums]

        elapsed = (time.time() - start) * 1000
        logger.info(f"RAG 完成: 耗时 {elapsed:.0f}ms, 引用 {len(valid_citations)} 条")

        return {
            "answer": answer,
            "citations": valid_citations,
            "token_usage": result["usage"],
            "processing_time_ms": elapsed,
        }

    async def ask_stream(self, question: str, kb_id: UUID):
        """
        RAG 问答（流式 SSE）

        产生 SSE 事件:
            event: token    — 生成的文本片段
            event: citation — 引用列表
            event: done     — 完成
            event: error    — 错误

        Yields:
            SSE 格式的事件字符串
        """
        import json

        start = time.time()

        try:
            # Step 1: 检索
            docs = await self.retrieval.retrieve(question, kb_id)
            if not docs:
                yield f'event: error\ndata: {{"code": 400, "message": "根据现有资料，无法回答这个问题"}}\n\n'
                return

            # Step 2: 组装 Context
            context_parts = []
            citations = []
            for i, doc in enumerate(docs):
                idx = i + 1
                title = doc.get("document_title", "未知文档")
                content = doc.get("content", "")
                context_parts.append(f"[{idx}] {title}\n{content}")
                citations.append({
                    "index": idx,
                    "document_title": title,
                    "chunk_id": doc.get("chunk_id", ""),
                    "content_snippet": content[:200],
                    "page_number": doc.get("page_number"),
                    "relevance_score": doc.get("score", 0),
                })

            context = "\n\n---\n\n".join(context_parts)

            # Step 3: Prompt
            system_prompt = PromptRegistry.render("rag_system")
            user_prompt = PromptRegistry.render("rag_user", context=context, question=question)

            # Step 4: 流式生成
            full_answer = ""
            async for token in self.llm_client.generate_stream([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]):
                full_answer += token
                yield f"event: token\ndata: {json.dumps({'content': token})}\n\n"

            # Step 5: 引用
            yield f"event: citation\ndata: {json.dumps({'citations': citations})}\n\n"

            elapsed = (time.time() - start) * 1000
            yield f"event: done\ndata: {json.dumps({'processing_time_ms': elapsed})}\n\n"

        except Exception as e:
            logger.error(f"RAG 流式生成错误: {e}", exc_info=True)
            yield f'event: error\ndata: {{"code": 500, "message": "AI 服务暂不可用: {str(e)}"}}\n\n'
