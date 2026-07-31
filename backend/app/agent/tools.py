"""L4 Agent 工具层 — PDF 能力工具化

不把整个 PDF 塞进上下文，而是把 PDF 能力封装成五个工具，
Agent 按意图按需调用：

- ``search_pdf``    语义检索相关片段（复用 hybrid pipeline + metadata 过滤）
- ``read_page``     读取指定页完整内容（精读）
- ``extract_table`` 抽取结构化表格（行列 JSON，不让模型猜文本化表格）
- ``analyze_chart`` 对图表调视觉模型做深度分析（趋势、对比、异常点）
- ``quote_source``  返回可展示引用：页码 + 章节 + 原文片段
"""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy import select

from app.core.logger import get_logger
from app.models.database.document import Document, DocumentChunk
from app.parsers.pdf.models import DocumentStructure

logger = get_logger(__name__)


class PDFTools:
    """PDF 工具集 — 每个方法返回 JSON 可序列化 dict"""

    def __init__(self, session, retrieval_pipeline=None, llm_client=None):
        self.session = session
        self.pipeline = retrieval_pipeline
        self.llm_client = llm_client
        self._structure_cache: dict[str, DocumentStructure] = {}

    # ---- 内部：文档结构缓存 ------------------------------------------
    async def _get_structure(self, doc_id: UUID) -> DocumentStructure:
        key = str(doc_id)
        if key in self._structure_cache:
            return self._structure_cache[key]
        doc = await self.session.get(Document, doc_id)
        if not doc or not doc.file_path or not os.path.exists(doc.file_path):
            raise ValueError(f"文档不存在或文件已丢失: {doc_id}")
        from app.parsers.pdf_parser import PDFParser

        structure = PDFParser().parse_structured(doc.file_path)
        self._structure_cache[key] = structure
        return structure

    # ---- 工具 1：search_pdf ------------------------------------------
    async def search_pdf(
        self,
        query: str,
        kb_id: UUID,
        filters: dict | None = None,
        limit: int = 5,
    ) -> dict:
        """语义检索相关片段，支持 kind/section/pages 过滤"""
        if self.pipeline is None:
            raise ValueError("检索管线未配置")
        results = await self.pipeline.retrieve(
            query, kb_id, rerank_top_k=max(limit * 2, 8)
        )
        filters = filters or {}
        kind = filters.get("kind")
        section = filters.get("section")
        pages = filters.get("pages")  # [start, end]

        def _hit(r: dict) -> bool:
            if kind and r.get("kind") != kind:
                return False
            if section and section not in (r.get("section_path") or ""):
                return False
            if pages:
                ps, pe = r.get("page_start"), r.get("page_end")
                if ps is None or pe is None:
                    return False
                if pe < pages[0] or ps > pages[1]:
                    return False
            return True

        hits = [r for r in results if _hit(r)][:limit]
        return {
            "query": query,
            "count": len(hits),
            "chunks": [{
                "chunk_id": r.get("chunk_id"),
                "document_id": r.get("document_id"),
                "document_title": r.get("document_title"),
                "content": (r.get("content") or "")[:500],
                "page_start": r.get("page_start"),
                "page_end": r.get("page_end"),
                "section_path": r.get("section_path"),
                "kind": r.get("kind"),
                "table_id": r.get("table_id"),
            } for r in hits],
        }

    # ---- 工具 2：read_page -------------------------------------------
    async def read_page(self, doc_id: UUID, page_no: int) -> dict:
        """读取指定页完整内容（正文 + 表格 + 图表占位）"""
        structure = await self._get_structure(doc_id)
        if page_no < 1 or page_no > structure.page_count:
            raise ValueError(f"页码越界: {page_no}（文档共 {structure.page_count} 页）")

        texts, tables, figures = [], [], 0
        for node in structure.nodes:
            if not (node.page_start <= page_no <= node.page_end):
                continue
            if node.kind == "table" and node.table:
                tables.append({
                    "table_id": node.table.table_id,
                    "caption": node.table.caption,
                    "headers": node.table.headers,
                    "rows": node.table.rows,
                })
            elif node.kind == "figure":
                figures += 1
                if node.text.strip():
                    texts.append(f"[图表描述] {node.text}")
            elif node.text.strip():
                texts.append(node.text)

        return {
            "doc_id": str(doc_id),
            "page_no": page_no,
            "page_count": structure.page_count,
            "text": "\n".join(texts),
            "tables": tables,
            "figure_count": figures,
        }

    # ---- 工具 3：extract_table ---------------------------------------
    async def extract_table(
        self,
        doc_id: UUID,
        table_id: str | None = None,
        page_no: int | None = None,
    ) -> dict:
        """抽取结构化表格：返回行列 JSON 而非文本"""
        structure = await self._get_structure(doc_id)
        matched = []
        for node in structure.nodes:
            if node.kind != "table" or not node.table:
                continue
            t = node.table
            if table_id and t.table_id != table_id:
                continue
            if page_no and node.page_start != page_no:
                continue
            matched.append({
                "table_id": t.table_id,
                "caption": t.caption,
                "page": node.page_start,
                "section_path": node.section_path,
                "headers": t.headers,
                "rows": t.rows,
                "row_count": len(t.rows),
            })
        return {"doc_id": str(doc_id), "count": len(matched), "tables": matched}

    # ---- 工具 4：analyze_chart ---------------------------------------
    async def analyze_chart(
        self,
        doc_id: UUID,
        page_no: int,
        figure_index: int = 0,
    ) -> dict:
        """对指定页的图表调视觉模型做深度分析"""
        structure = await self._get_structure(doc_id)
        figures = [
            n for n in structure.nodes
            if n.kind == "figure" and n.page_start == page_no
        ]
        if not figures:
            return {"doc_id": str(doc_id), "page_no": page_no,
                    "analysis": None, "error": "该页没有图表"}
        if figure_index >= len(figures):
            raise ValueError(f"图表序号越界: {figure_index}（该页共 {len(figures)} 个图表）")

        node = figures[figure_index]
        if self.llm_client is None:
            return {"doc_id": str(doc_id), "page_no": page_no,
                    "analysis": None, "error": "视觉模型未配置"}

        from app.parsers.pdf.vision_extractor import analyze_figure

        doc = await self.session.get(Document, doc_id)
        analysis = await analyze_figure(self.llm_client, doc.file_path, node)
        if not analysis and node.text.strip():
            analysis = node.text  # 入库时视觉理解已生成过描述，直接复用
        return {
            "doc_id": str(doc_id),
            "page_no": page_no,
            "figure_index": figure_index,
            "section_path": node.section_path,
            "analysis": analysis,
            "error": None if analysis else "视觉模型分析失败",
        }

    # ---- 工具 5：quote_source ----------------------------------------
    async def quote_source(self, chunk_id: UUID) -> dict:
        """返回可展示引用：页码 + 章节 + 原文片段"""
        result = await self.session.execute(
            select(DocumentChunk, Document.title)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(DocumentChunk.id == chunk_id)
        )
        row = result.first()
        if not row:
            raise ValueError(f"chunk 不存在: {chunk_id}")
        chunk, doc_title = row
        meta = chunk.metadata_ or {}
        section = meta.get("section_path") or chunk.section_title
        if isinstance(section, list):
            section = " / ".join(section)
        return {
            "chunk_id": str(chunk_id),
            "document_title": doc_title,
            "page_start": chunk.page_number or meta.get("page_start"),
            "page_end": meta.get("page_end") or chunk.page_number,
            "section_path": section,
            "kind": meta.get("kind"),
            "clause_no": meta.get("clause_no"),
            "snippet": (chunk.content or "")[:300],
        }
