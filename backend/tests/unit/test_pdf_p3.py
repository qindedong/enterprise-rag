"""P3 单元测试：视觉理解 + Agent 工具层 + 意图路由

全部使用 Fake 对象，不依赖真实 LLM/视觉 API/数据库。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import fitz
import pytest

from app.agent.planner import PDFAgent, route_intent
from app.agent.tools import PDFTools
from app.parsers.pdf.models import DocumentStructure, StructNode
from app.parsers.pdf.vision_extractor import analyze_figure, analyze_figures
from app.rag.semantic_chunker import SemanticChunker


# ---- 样本：一页带图片的 PDF -------------------------------------------
def _make_figure_pdf(path) -> None:
    tmp = fitz.open()
    tpage = tmp.new_page()
    tpage.draw_rect(fitz.Rect(60, 180, 130, 400), fill=(0.4, 0.6, 0.9))
    pix = tpage.get_pixmap(clip=fitz.Rect(0, 100, 300, 450))
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 40, 545, 100),
                        "第六章 经营分析\n本年度四个季度的收入呈现明显的波动上升趋势，"
                        "其中第四季度收入最高，较第一季度增长约一倍，"
                        "主要得益于新产品线的放量。下图展示各季度收入对比。",
                        fontsize=12, fontname="china-s")
    page.insert_image(fitz.Rect(80, 150, 380, 500), pixmap=pix)
    doc.save(path)


class FakeVisionLLM:
    async def generate_with_image(self, prompt, image_bytes, mime="image/png"):
        assert image_bytes[:4] == b"\x89PNG"
        return {"answer": "柱状图展示四个季度收入，第四季度最高。"}


class FailVisionLLM:
    async def generate_with_image(self, prompt, image_bytes, mime="image/png"):
        raise RuntimeError("vision api down")


def _figure_structure() -> DocumentStructure:
    return DocumentStructure(
        file_path="", page_count=1,
        nodes=[StructNode(kind="figure", text="", page_start=1, page_end=1,
                          section_path=["第六章 经营分析"],
                          figure_bbox=(80, 150, 380, 500))],
    )


# ================= 视觉理解 =================

class TestVisionExtractor:
    @pytest.mark.asyncio
    async def test_analyze_figures_fills_text(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_figure_pdf(pdf)
        structure = _figure_structure()
        done = await analyze_figures(FakeVisionLLM(), str(pdf), structure)
        assert done == 1
        assert "第四季度" in structure.nodes[0].text

    @pytest.mark.asyncio
    async def test_analyze_figures_failure_keeps_placeholder(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_figure_pdf(pdf)
        structure = _figure_structure()
        done = await analyze_figures(FailVisionLLM(), str(pdf), structure)
        assert done == 0
        assert structure.nodes[0].text == ""

    @pytest.mark.asyncio
    async def test_analyze_figure_bad_bbox_returns_none(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_figure_pdf(pdf)
        node = StructNode(kind="figure", text="", page_start=1, page_end=1,
                          figure_bbox=(-100, -100, -50, -50))
        assert await analyze_figure(FakeVisionLLM(), str(pdf), node) is None

    def test_figure_summary_chunk_carries_description(self):
        structure = _figure_structure()
        structure.nodes[0].text = "柱状图展示四个季度收入，第四季度最高。"
        chunks = SemanticChunker().split(structure)
        fig = [c for c in chunks if c.kind == "figure_summary"]
        assert fig and "第四季度最高" in fig[0].text
        assert "第六章 经营分析" in fig[0].text


# ================= 意图路由 =================

class TestRouteIntent:
    @pytest.mark.parametrize("q,want", [
        ("迟到扣多少钱？", "simple"),
        ("这句话出自哪里？", "quote"),
        ("各项费用占比是多少？", "chart"),
        ("费用明细表格里开发费是多少？", "table"),
        ("对比第一章和第四章的违约责任", "compare"),
    ])
    def test_routing(self, q, want):
        assert route_intent(q) == want


# ================= PDFTools =================

class FakePipeline:
    def __init__(self, results):
        self._results = results

    async def retrieve(self, question, kb_id, **kw):
        return self._results


def _fake_session(file_path: str):
    doc = SimpleNamespace(file_path=file_path)
    session = SimpleNamespace()
    session.get = AsyncMock(return_value=doc)
    return session


class TestPDFTools:
    @pytest.mark.asyncio
    async def test_search_pdf_filters_kind_and_pages(self):
        results = [
            {"chunk_id": "1", "document_title": "a.pdf", "content": "x",
             "page_start": 1, "page_end": 1, "section_path": "第一章",
             "kind": "clause"},
            {"chunk_id": "2", "document_title": "a.pdf", "content": "y",
             "page_start": 5, "page_end": 5, "section_path": "第二章",
             "kind": "table"},
        ]
        tools = PDFTools(None, FakePipeline(results))
        r = await tools.search_pdf("q", uuid4(), filters={"kind": "table"})
        assert r["count"] == 1 and r["chunks"][0]["chunk_id"] == "2"
        r = await tools.search_pdf("q", uuid4(), filters={"pages": [1, 3]})
        assert r["count"] == 1 and r["chunks"][0]["chunk_id"] == "1"
        r = await tools.search_pdf("q", uuid4(), filters={"section": "第二章"})
        assert r["count"] == 1

    @pytest.mark.asyncio
    async def test_read_page_and_out_of_range(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_figure_pdf(pdf)
        tools = PDFTools(_fake_session(str(pdf)))
        r = await tools.read_page(uuid4(), 1)
        assert "收入" in r["text"] and r["figure_count"] == 1
        with pytest.raises(ValueError, match="页码越界"):
            await tools.read_page(uuid4(), 99)

    @pytest.mark.asyncio
    async def test_analyze_chart_uses_cached_description(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_figure_pdf(pdf)
        tools = PDFTools(_fake_session(str(pdf)), llm_client=FakeVisionLLM())
        r = await tools.analyze_chart(uuid4(), 1)
        assert r["analysis"] and "第四季度" in r["analysis"]
        assert r["error"] is None

    @pytest.mark.asyncio
    async def test_analyze_chart_no_figure(self, tmp_path):
        pdf = tmp_path / "text.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 545, 800),
                            "纯文字页面，没有任何图片内容。" * 20,
                            fontsize=12, fontname="china-s")
        doc.save(pdf)
        tools = PDFTools(_fake_session(str(pdf)), llm_client=FakeVisionLLM())
        r = await tools.analyze_chart(uuid4(), 1)
        assert r["analysis"] is None and "没有图表" in r["error"]


# ================= PDFAgent 编排 =================

class FakeRAGService:
    def __init__(self):
        self.llm_client = SimpleNamespace(generate=AsyncMock(
            return_value={"answer": "综合结论"}))

    async def ask(self, question, kb_id, *a, **kw):
        return {"answer": "直接回答", "citations": [],
                "token_usage": {}, "processing_time_ms": 1.0}


class TestPDFAgent:
    @pytest.mark.asyncio
    async def test_simple_passthrough(self):
        agent = PDFAgent(FakeRAGService(), PDFTools(None))
        r = await agent.answer("迟到扣多少钱？", uuid4())
        assert r["intent"] == "simple" and r["answer"] == "直接回答"

    @pytest.mark.asyncio
    async def test_chart_intent_uses_tools(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_figure_pdf(pdf)
        doc_id = str(uuid4())
        pipeline = FakePipeline([{
            "chunk_id": "1", "document_id": doc_id, "document_title": "fig.pdf",
            "content": "[图片/图表]", "page_start": 1, "page_end": 1,
            "section_path": "第六章", "kind": "figure_summary"}])
        tools = PDFTools(_fake_session(str(pdf)), pipeline, FakeVisionLLM())
        agent = PDFAgent(FakeRAGService(), tools)
        r = await agent.answer("收入趋势图说明了什么？", uuid4())
        assert r["intent"] == "chart"
        assert "search_pdf" in r["tools_used"] and "analyze_chart" in r["tools_used"]
        assert r["citations"][0]["page_start"] == 1

    @pytest.mark.asyncio
    async def test_tool_failure_falls_back(self):
        pipeline = FakePipeline([{
            "chunk_id": None, "document_id": str(uuid4()),
            "document_title": "x.pdf", "content": "c",
            "page_start": 1, "page_end": 1, "section_path": "", "kind": "table"}])
        tools = PDFTools(None, pipeline)  # session=None → extract_table 必炸
        agent = PDFAgent(FakeRAGService(), tools)
        r = await agent.answer("费用明细表格里开发费是多少？", uuid4())
        assert "fallback" in r["intent"] and r["answer"] == "直接回答"

    @pytest.mark.asyncio
    async def test_max_steps_guard(self):
        pipeline = FakePipeline([
            {"chunk_id": str(uuid4()), "document_title": "a.pdf", "content": "x",
             "page_start": 1, "page_end": 1, "section_path": "", "kind": "clause"}
            for _ in range(10)])
        tools = PDFTools(None, pipeline)
        agent = PDFAgent(FakeRAGService(), tools, max_steps=2)
        r = await agent.answer("这句话出自哪里？", uuid4())
        # quote 路径 3 个 chunk × quote_source 必然超 2 步 → 兜底回退
        assert "fallback" in r["intent"]
