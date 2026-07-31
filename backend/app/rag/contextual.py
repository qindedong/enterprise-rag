"""L3 Contextual Retrieval — 给每个 chunk 生成语义上下文前缀（Anthropic 思路）

文档入库时，由 LLM 为每个 chunk 生成一两句出处说明并前置拼接，
再参与向量化和 BM25 索引。歧义片段（"第三条"、"如上所述"）的召回
率显著提升。生成是入库时的一次性成本，查询零额外延迟。

降级保护：LLM 不可用/生成失败时保留 P0 的机械章节前缀，不阻塞入库。
"""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger
from app.rag.semantic_chunker import StructuredChunk

logger = get_logger(__name__)

MAX_CONTEXT_CHARS = 120       # 生成说明的最大长度（超出截断）
CONTENT_PREVIEW_CHARS = 800   # 送给 LLM 的片段预览长度
CONCURRENCY = 4               # 并发生成数（避免触发 LLM 限流）

_SYSTEM_PROMPT = (
    "你是检索增强系统的上下文标注器。给定文档名、章节路径和一个文档片段，"
    "用一两句话说明该片段出自哪份文档的哪个部分、讲了什么主题，"
    "用于提升检索准确性。要求：不超过 60 字；只输出说明文字本身；"
    "不复述片段内容；不使用引号。"
)


class Contextualizer:
    """chunk 上下文注入器"""

    def __init__(self, llm_client, concurrency: int = CONCURRENCY):
        self.llm = llm_client
        self._sem = asyncio.Semaphore(concurrency)

    async def _gen_one(self, chunk: StructuredChunk, doc_title: str) -> str | None:
        """为单个 chunk 生成上下文说明，失败返回 None"""
        section = " / ".join(chunk.section_path) or "未分章节"
        meta = chunk.kind
        if chunk.clause_no:
            meta += f"（{chunk.clause_no}）"
        user = (
            f"文档：《{doc_title}》\n"
            f"章节：{section}\n"
            f"片段类型：{meta}\n"
            f"片段内容：\n{chunk.text[:CONTENT_PREVIEW_CHARS]}"
        )
        try:
            async with self._sem:
                result = await self.llm.generate([
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user},
                ])
            context = (result.get("answer") or "").strip()
            # 清洗：去引号/换行/超长截断
            context = context.replace("\n", " ").strip('"\'「」')
            if not context or len(context) < 8:
                return None
            return context[:MAX_CONTEXT_CHARS]
        except Exception as e:
            logger.warning(f"上下文生成失败（chunk {chunk.page_start} 页）: {e}")
            return None

    async def add_context(
        self, chunks: list[StructuredChunk], doc_title: str
    ) -> int:
        """为全部 chunk 注入上下文前缀（原地修改 text），返回成功注入数

        注入方式：若 chunk 文本以机械章节前缀开头则剥除，
        替换为语义化说明 "[说明]\n正文"；失败 chunk 保持原样。
        """
        if not chunks:
            return 0

        results = await asyncio.gather(
            *(self._gen_one(c, doc_title) for c in chunks)
        )

        injected = 0
        for chunk, context in zip(chunks, results, strict=True):
            if not context:
                continue
            section_prefix = " / ".join(chunk.section_path)
            body = chunk.text
            if section_prefix and body.startswith(section_prefix):
                body = body[len(section_prefix):].lstrip("\n")
            chunk.text = f"[{context}]\n{body}"
            chunk.context_prefix = context
            injected += 1

        logger.info(f"Contextual Retrieval: {injected}/{len(chunks)} 个 chunk 注入上下文")
        return injected
