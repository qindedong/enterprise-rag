"""P1 测试：表格结构化（find_tables）+ 条款边界切片

测试 PDF 全部用 PyMuPDF 动态生成（手绘表格线可被 find_tables 检测）。
"""

import fitz
import pytest

from app.parsers.pdf.models import PageType, StructuredTable
from app.parsers.pdf.tables import block_in_table, extract_tables, find_caption
from app.parsers.pdf.models import Block
from app.parsers.pdf_parser import PDFParser
from app.rag.semantic_chunker import SemanticChunker


def _make_table_pdf(path, caption="表 1 主要财务指标", extra_rows=0):
    """生成含 3 列线框表格的单页 PDF（caption + 表头 + 2+N 数据行）

    extra_rows 较多时使用紧凑行距，保证表格画在页面范围内。
    """
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 60), caption, fontsize=14, fontname="china-s")
    n_rows = 3 + extra_rows
    row_h = 50 if n_rows <= 12 else 12
    font_size = 10 if n_rows <= 12 else 6
    y_end = 100 + n_rows * row_h
    for x in (100, 200, 300, 400):
        page.draw_line((x, 100), (x, y_end))
    for i in range(n_rows + 1):
        page.draw_line((100, 100 + i * row_h), (400, 100 + i * row_h))
    cells = [["指标", "2023", "2024"],
             ["营收（亿元）", "152.3", "178.6"],
             ["净利润（亿元）", "18.2", "21.5"]]
    cells += [[f"指标{i}", f"{i}.1", f"{i}.2"] for i in range(3, 3 + extra_rows)]
    for r, row in enumerate(cells):
        for c, val in enumerate(row):
            page.insert_text((105 + c * 100, 100 + (r + 0.65) * row_h), val,
                             fontsize=font_size, fontname="china-s")
    page.insert_text((72, min(y_end + 40, 780)), "表格下方的正文段落。", fontsize=12,
                     fontname="china-s")
    doc.save(str(path))
    doc.close()


@pytest.mark.unit
class TestTableExtraction:
    def test_extract_headers_and_rows(self, tmp_path):
        pdf = tmp_path / "t.pdf"
        _make_table_pdf(pdf)
        doc = fitz.open(str(pdf))
        tables = extract_tables(doc[0], 1)
        doc.close()
        assert len(tables) == 1
        t = tables[0]
        assert t.headers == ["指标", "2023", "2024"]
        assert len(t.rows) == 2
        assert t.rows[0] == ["营收（亿元）", "152.3", "178.6"]

    def test_block_in_table(self, tmp_path):
        pdf = tmp_path / "t.pdf"
        _make_table_pdf(pdf)
        doc = fitz.open(str(pdf))
        tables = extract_tables(doc[0], 1)
        inside = Block(kind="text", bbox=(150, 160, 190, 180), text="152.3", page_no=1)
        outside = Block(kind="text", bbox=(72, 400, 200, 420), text="正文", page_no=1)
        assert block_in_table(inside, tables)
        assert not block_in_table(outside, tables)
        doc.close()

    def test_caption_assigned(self, tmp_path):
        pdf = tmp_path / "t.pdf"
        _make_table_pdf(pdf)
        structure = PDFParser().parse_structured(str(pdf))
        table_nodes = [n for n in structure.nodes if n.kind == "table"]
        assert len(table_nodes) == 1
        assert table_nodes[0].table.caption == "表 1 主要财务指标"

    def test_cell_text_not_in_paragraph_stream(self, tmp_path):
        pdf = tmp_path / "t.pdf"
        _make_table_pdf(pdf)
        structure = PDFParser().parse_structured(str(pdf))
        paras = [n for n in structure.nodes if n.kind == "paragraph"]
        # 单元格文本（152.3 等）不应出现在段落流
        assert all("152.3" not in n.text and "178.6" not in n.text for n in paras)
        # 表后正文仍在段落流
        assert any("表格下方的正文段落" in n.text for n in paras)


@pytest.mark.unit
class TestTableChunk:
    def test_table_chunk_structured_text(self, tmp_path):
        pdf = tmp_path / "t.pdf"
        _make_table_pdf(pdf)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker().split(structure)
        tchunks = [c for c in chunks if c.kind == "table"]
        assert len(tchunks) == 1
        c = tchunks[0]
        # 数字绑定指标与年份
        assert "2024=178.6" in c.text
        assert "营收" in c.text
        assert c.table_id
        assert "表格：表 1 主要财务指标" in c.text

    def test_long_table_split_repeats_header(self, tmp_path):
        pdf = tmp_path / "t.pdf"
        _make_table_pdf(pdf, extra_rows=60)  # 62 数据行，必超限
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker(chunk_size=500).split(structure)
        tchunks = [c for c in chunks if c.kind == "table"]
        assert len(tchunks) >= 2
        # 每个分组 chunk 都重复表头
        for c in tchunks:
            assert "表头：指标 | 2023 | 2024" in c.text


@pytest.mark.unit
class TestClauseBoundary:
    def _clause_pdf(self, tmp_path, clause_body_len=150):
        pdf = tmp_path / "clauses.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "第五章 考勤制度", fontsize=16, fontname="china-s")
        body = "员工应当遵守公司考勤管理规定，按时上下班。" * (clause_body_len // 20)
        y = 120
        for n, cn in [(12, "十二"), (13, "十三"), (14, "十四")]:
            page.insert_textbox(
                fitz.Rect(72, y, 540, y + 300),
                f"第{cn}条 {body}", fontsize=12, fontname="china-s")
            y += 320
            if y > 700:
                page = doc.new_page()
                y = 72
        doc.set_toc([[1, "第五章 考勤制度", 1]])
        doc.save(str(pdf))
        doc.close()
        return pdf

    def test_clause_never_split(self, tmp_path):
        pdf = self._clause_pdf(tmp_path)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker(chunk_size=300).split(structure)
        clause_chunks = [c for c in chunks if c.kind == "clause"]
        assert clause_chunks
        for c in clause_chunks:
            # 含条款开头的 chunk，其条款正文必须完整（以句号收尾）
            if "第" in c.text and "条" in c.text:
                assert c.text.rstrip().endswith("。")

    def test_single_clause_chunk_has_clause_no(self, tmp_path):
        pdf = self._clause_pdf(tmp_path, clause_body_len=400)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker(chunk_size=500).split(structure)
        numbered = [c for c in chunks if c.clause_no]
        assert numbered, "单条款 chunk 应标注条款号"
        for c in numbered:
            assert c.clause_no.startswith("第") and c.clause_no.endswith("条")

    def test_short_clauses_merge_at_boundary(self, tmp_path):
        pdf = tmp_path / "short.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "第一章 总则", fontsize=16, fontname="china-s")
        page.insert_text((72, 120), "第一条 本制度自发布之日起施行。", fontsize=12,
                         fontname="china-s")
        page.insert_text((72, 160), "第二条 本制度由人力资源部负责解释。", fontsize=12,
                         fontname="china-s")
        doc.set_toc([[1, "第一章 总则", 1]])
        doc.save(str(pdf))
        doc.close()
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker(chunk_size=500).split(structure)
        # 两个短条款合并为一个 chunk，且合并只在条款边界发生
        assert len(chunks) == 1
        c = chunks[0]
        assert "第一条" in c.text and "第二条" in c.text
        assert c.kind == "clause"
        assert c.clause_no is None  # 多条款合并不标注单一条款号
