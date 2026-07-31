"""P2 测试：OCR 路径（RapidOCR）+ Contextual Retrieval 上下文注入"""

import fitz
import pytest

from app.parsers.pdf.models import PageType
from app.parsers.pdf_parser import PDFParser
from app.rag.semantic_chunker import SemanticChunker, StructuredChunk


def _make_scanned_text_pdf(path, text="公司考勤制度：员工迟到按月累计，三次以内每次扣款五十元。"):
    """生成"文字扫描件"：先把文字渲染成图片，再插入新 PDF（无文字层）"""
    # 1. 渲染带文字的页面为图片
    src = fitz.open()
    spage = src.new_page()
    spage.insert_textbox(fitz.Rect(72, 100, 520, 500), text,
                         fontsize=20, fontname="china-s")
    pix = spage.get_pixmap(matrix=fitz.Matrix(2, 2))
    png = pix.tobytes("png")
    src.close()
    # 2. 图片插入新 PDF（模拟扫描件）
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=png)
    doc.save(str(path))
    doc.close()


@pytest.mark.unit
class TestOcrPath:
    def test_scanned_pdf_text_recovered(self, tmp_path):
        """扫描件经 OCR 还原文字，块带坐标与置信度"""
        pytest.importorskip("rapidocr_onnxruntime", reason="OCR 依赖未安装")
        pdf = tmp_path / "scan.pdf"
        _make_scanned_text_pdf(pdf)

        structure = PDFParser().parse_structured(str(pdf))

        assert structure.page_types[1] == PageType.SCANNED
        paras = [n for n in structure.nodes if n.kind == "paragraph"]
        full = "\n".join(n.text for n in paras)
        assert "考勤" in full, f"OCR 应识别出考勤相关内容，实际: {full[:80]}"
        assert structure.nodes, "扫描件经 OCR 后应有结构节点"

    def test_scanned_chunk_searchable(self, tmp_path):
        """扫描件 OCR → 切片全链路可用"""
        pytest.importorskip("rapidocr_onnxruntime", reason="OCR 依赖未安装")
        pdf = tmp_path / "scan2.pdf"
        _make_scanned_text_pdf(pdf)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker().split(structure)
        text_all = " ".join(c.text for c in chunks if c.kind != "figure_summary")
        assert "考勤" in text_all or "迟到" in text_all


@pytest.mark.unit
class TestContextual:
    def _chunk(self, text="第十三条 乙方违反竞业限制约定的，应当支付违约金。",
               section_path=None):
        return StructuredChunk(
            text=text,
            page_start=3, page_end=3,
            section_path=section_path or ["第三章 违约责任"],
            kind="clause", clause_no="第13条",
        )

    @pytest.mark.asyncio
    async def test_context_injected_and_prefix_replaced(self):
        """注入语义上下文，机械章节前缀被替换"""
        from app.rag.contextual import Contextualizer

        class FakeLLM:
            async def generate(self, messages):
                return {"answer": "本片段出自《劳动合同》第三章违约责任第13条，规定竞业限制违约后果。"}

        chunk = self._chunk(
            text="第三章 违约责任\n第十三条 乙方违反竞业限制约定的，应当支付违约金。"
        )
        c = Contextualizer(FakeLLM())
        n = await c.add_context([chunk], "劳动合同.pdf")
        assert n == 1
        assert chunk.text.startswith("[本片段出自《劳动合同》")
        assert "第十三条" in chunk.text
        # 机械前缀行被剥除（正文完整保留）
        assert not chunk.text.startswith("第三章 违约责任\n")
        assert "应当支付违约金" in chunk.text
        assert chunk.context_prefix

    @pytest.mark.asyncio
    async def test_llm_failure_keeps_original(self):
        """LLM 失败时 chunk 保持原样，不阻塞入库"""
        from app.rag.contextual import Contextualizer

        class FailLLM:
            async def generate(self, messages):
                raise RuntimeError("LLM 限流")

        chunk = self._chunk()
        original = chunk.text
        c = Contextualizer(FailLLM())
        n = await c.add_context([chunk], "劳动合同.pdf")
        assert n == 0
        assert chunk.text == original

    @pytest.mark.asyncio
    async def test_short_answer_rejected(self):
        """过短/空的 LLM 返回视为失败"""
        from app.rag.contextual import Contextualizer

        class EmptyLLM:
            async def generate(self, messages):
                return {"answer": "  "}

        chunk = self._chunk()
        c = Contextualizer(EmptyLLM())
        n = await c.add_context([chunk], "doc.pdf")
        assert n == 0
        assert chunk.context_prefix is None
