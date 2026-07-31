"""L4 意图路由与多步规划 — 在现有 RAGService 上的薄 Agent 编排层

路由策略（确定性规则，不引入重型 Agent 框架）：

| 用户意图 | 路由 |
|----------|------|
| 简单事实 | 直通现有检索管线（零改动、零额外延迟） |
| 复杂对比 | search_pdf 多轮检索多个对象 → LLM 综合 |
| 表格问题 | extract_table 返回结构化行列，不让模型猜文本 |
| 图表问题 | analyze_chart 调视觉模型深度分析 |
| 溯源请求 | quote_source 返回精确引用 |

所有路径共享 ``AGENT_MAX_STEPS`` 步数上限兜底。
"""

from __future__ import annotations

import re
import time
from uuid import UUID

from app.core.logger import get_logger

logger = get_logger(__name__)

# 意图规则：按优先级从上到下匹配，先中先得
INTENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("quote", ("出自", "来源", "引用", "哪里说", "原文", "依据是什么")),
    ("chart", ("图表", "趋势", "占比", "饼图", "柱状", "折线", "流程图", "走势图")),
    ("table", ("表格", "明细", "一览", "各项费用", "各项数据")),
    ("compare", ("对比", "比较", "区别", "差异", "哪个更")),
]

# 对比问题的对象切分词
_COMPARE_SPLIT = re.compile(r"对比|比较|和|与|跟|、|，|,")


def route_intent(question: str) -> str:
    """规则路由：返回 simple | quote | chart | table | compare"""
    for intent, keywords in INTENT_RULES:
        if any(kw in question for kw in keywords):
            return intent
    return "simple"


class PDFAgent:
    """PDF 问答 Agent — 按意图编排工具调用"""

    def __init__(self, rag_service, tools, max_steps: int = 6):
        self.rag_service = rag_service
        self.tools = tools
        self.max_steps = max_steps
        self._steps = 0

    async def answer(self, question: str, kb_id: UUID) -> dict:
        """按意图路由到对应工具链，返回 {answer, citations, intent, tools_used}"""
        start = time.time()
        self._steps = 0
        intent = route_intent(question)
        tools_used: list[str] = []

        try:
            if intent == "simple":
                result = await self.rag_service.ask(question, kb_id)
                result["intent"] = "simple"
                result["tools_used"] = []
                return result

            handler = {
                "quote": self._handle_quote,
                "chart": self._handle_chart,
                "table": self._handle_table,
                "compare": self._handle_compare,
            }[intent]
            answer, citations = await handler(question, kb_id, tools_used)
            if answer is None:
                # 工具链未命中（如图表视觉不可用、无表格），回退常规检索问答
                raise LookupError(f"{intent} 工具链无结果")
        except Exception as e:
            logger.warning(f"Agent 工具链失败，回退简单问答: {e}")
            result = await self.rag_service.ask(question, kb_id)
            result["intent"] = f"{intent}->fallback"
            result["tools_used"] = tools_used
            return result

        return {
            "answer": answer,
            "citations": citations,
            "intent": intent,
            "tools_used": tools_used,
            "token_usage": {},
            "processing_time_ms": (time.time() - start) * 1000,
        }

    def _step(self, tools_used: list[str], name: str) -> None:
        self._steps += 1
        tools_used.append(name)
        if self._steps > self.max_steps:
            raise RuntimeError(f"Agent 步数超过上限 {self.max_steps}")

    # ---- 溯源：quote_source ------------------------------------------
    async def _handle_quote(self, question, kb_id, tools_used):
        hits = await self.tools.search_pdf(question, kb_id, limit=3)
        self._step(tools_used, "search_pdf")
        citations = []
        for c in hits["chunks"]:
            if not c.get("chunk_id"):
                continue
            self._step(tools_used, "quote_source")
            citations.append(await self.tools.quote_source(UUID(c["chunk_id"])))
        if not citations:
            return None, []
        lines = ["该内容的相关出处如下："]
        for i, q in enumerate(citations, 1):
            page = f"第 {q['page_start']} 页" if q.get("page_start") else "页码未知"
            section = q.get("section_path") or "未分章节"
            lines.append(f"[{i}] 《{q['document_title']}》{page}，{section}：{q['snippet'][:80]}…")
        return "\n".join(lines), citations

    # ---- 图表：analyze_chart -----------------------------------------
    async def _handle_chart(self, question, kb_id, tools_used):
        hits = await self.tools.search_pdf(
            question, kb_id, filters={"kind": "figure_summary"}, limit=3
        )
        self._step(tools_used, "search_pdf")
        analyses = []
        for c in hits["chunks"]:
            if not c.get("document_id") or not c.get("page_start"):
                continue
            self._step(tools_used, "analyze_chart")
            r = await self.tools.analyze_chart(UUID(c["document_id"]), c["page_start"])
            if r.get("analysis"):
                analyses.append({**r, "document_title": c.get("document_title")})
        if not analyses:
            return None, []
        return await self._synthesize(
            question,
            [f"《{a['document_title']}》第 {a['page_no']} 页图表分析：{a['analysis']}"
             for a in analyses],
        ), [{
            "chunk_id": None,
            "document_title": a.get("document_title"),
            "page_start": a.get("page_no"),
            "section_path": " / ".join(a.get("section_path") or []),
            "content_snippet": a["analysis"][:300],
        } for a in analyses]

    # ---- 表格：extract_table ------------------------------------------
    async def _handle_table(self, question, kb_id, tools_used):
        hits = await self.tools.search_pdf(
            question, kb_id, filters={"kind": "table"}, limit=3
        )
        self._step(tools_used, "search_pdf")
        contexts, citations = [], []
        seen = set()
        for c in hits["chunks"]:
            key = (c.get("document_id"), c.get("table_id"))
            if not key[0] or key in seen:
                continue
            seen.add(key)
            self._step(tools_used, "extract_table")
            r = await self.tools.extract_table(UUID(key[0]), table_id=key[1])
            for t in r["tables"]:
                header = "、".join(t.get("headers") or [])
                rows = [" | ".join(row) for row in t.get("rows") or []]
                contexts.append(
                    f"《{c.get('document_title')}》第 {t['page']} 页表格"
                    f"（{t.get('caption') or '无标题'}）：\n表头：{header}\n"
                    + "\n".join(rows[:20])
                )
                citations.append({
                    "chunk_id": c.get("chunk_id"),
                    "document_title": c.get("document_title"),
                    "page_start": t.get("page"),
                    "section_path": " / ".join(t.get("section_path") or []),
                    "content_snippet": (c.get("content") or "")[:300],
                })
        if not contexts:
            return None, []
        return await self._synthesize(question, contexts), citations

    # ---- 对比：多轮 search_pdf + 综合 ---------------------------------
    async def _handle_compare(self, question, kb_id, tools_used):
        parts = [p.strip("？?。 ") for p in _COMPARE_SPLIT.split(question) if p.strip("？?。 ")]
        sub_queries = parts[1:4] if len(parts) > 1 else [question]
        contexts, citations = [], []
        for q in sub_queries:
            self._step(tools_used, "search_pdf")
            hits = await self.tools.search_pdf(q, kb_id, limit=3)
            for c in hits["chunks"][:2]:
                contexts.append(
                    f"关于「{q}」：《{c.get('document_title')}》"
                    f"第 {c.get('page_start')} 页 {c.get('section_path') or ''}\n"
                    f"{c.get('content')}"
                )
                citations.append({
                    "chunk_id": c.get("chunk_id"),
                    "document_title": c.get("document_title"),
                    "page_start": c.get("page_start"),
                    "section_path": c.get("section_path"),
                    "content_snippet": (c.get("content") or "")[:300],
                })
        if not contexts:
            return None, []
        return await self._synthesize(
            question, contexts,
            instruction="请分别总结各方要点，再给出清晰的对比结论。",
        ), citations

    # ---- LLM 综合 -----------------------------------------------------
    async def _synthesize(self, question: str, contexts: list[str],
                          instruction: str = "") -> str:
        llm = self.rag_service.llm_client
        numbered = "\n\n".join(f"[资料 {i}] {c}" for i, c in enumerate(contexts, 1))
        prompt = (
            f"基于以下资料回答问题。{instruction or '请准确、简洁地回答。'}"
            "回答中引用资料时标注 [资料 N]。\n\n"
            f"{numbered}\n\n问题：{question}"
        )
        result = await llm.generate([
            {"role": "system", "content": "你是严谨的企业知识库助手，只依据给定资料回答。"},
            {"role": "user", "content": prompt},
        ])
        return (result.get("answer") or "").strip() or "资料不足，无法形成结论。"
