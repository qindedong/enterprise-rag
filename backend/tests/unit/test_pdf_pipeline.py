"""PDF 四层架构 P0 测试：L1 分类/抽取 + L2 结构还原 + L3 语义切片

测试 PDF 全部用 PyMuPDF 动态生成，无外部样本依赖。
"""

import fitz
import pytest

from app.parsers.pdf.classifier import classify_document
from app.parsers.pdf.models import PageType
from app.parsers.pdf.native_extractor import extract_document
from app.parsers.pdf.structure import (
    _cn_to_int,
    build_structure,
    filter_header_footer,
    normalize_clause_no,
    reorder_columns,
)
from app.parsers.pdf.models import PageContent, PageProfile
from app.parsers.pdf_parser import PDFParser
from app.rag.semantic_chunker import SemanticChunker


# ---------------------------------------------------------------- 工具

def _make_pdf(path, pages: list[list[tuple]], toc=None) -> None:
    """生成测试 PDF。pages[i] = [(text, x, y, fontsize), ...]"""
    doc = fitz.open()
    for blocks in pages:
        page = doc.new_page()
        for text, x, y, size in blocks:
            page.insert_text((x, y), text, fontsize=size, fontname="china-s")
    if toc:
        doc.set_toc(toc)
    doc.save(str(path))
    doc.close()


def _make_scanned_pdf(path) -> None:
    """生成无文字层、整页大图的扫描件 PDF"""
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 700, 900))
    pix.clear_with(230)  # 纯色灰底模拟扫描页
    png = pix.tobytes("png")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_image(page.rect, stream=png)
    doc.save(str(path))
    doc.close()


def _profile(page_no, page_type=PageType.NATIVE):
    return PageProfile(page_no=page_no, page_type=page_type,
                       text_length=100, image_coverage=0.0, image_count=0)


# ---------------------------------------------------------------- L1 分类

@pytest.mark.unit
class TestClassifier:
    def test_native_page(self, tmp_path):
        pdf = tmp_path / "native.pdf"
        _make_pdf(pdf, [[("这是一段正常的原生文本内容，字数足够多，超过五十个字符的阈值限制。" * 2, 72, 72, 12)]])
        doc = fitz.open(str(pdf))
        profiles = classify_document(doc)
        assert profiles[0].page_type == PageType.NATIVE
        doc.close()

    def test_scanned_page(self, tmp_path):
        pdf = tmp_path / "scan.pdf"
        _make_scanned_pdf(pdf)
        doc = fitz.open(str(pdf))
        profiles = classify_document(doc)
        assert profiles[0].page_type == PageType.SCANNED
        assert profiles[0].image_coverage > 0.7
        doc.close()

    def test_mixed_page(self, tmp_path):
        pdf = tmp_path / "mixed.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "本页包含文字和一张配图" * 6, fontsize=12, fontname="china-s")
        page.insert_text((72, 100), "第二行文字确保文字层超过五十字符的判定阈值。" * 2,
                         fontsize=12, fontname="china-s")
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 300, 200))
        pix.clear_with(180)
        page.insert_image(fitz.Rect(100, 300, 400, 500), stream=pix.tobytes("png"))
        doc.save(str(pdf))
        doc.close()

        doc = fitz.open(str(pdf))
        profiles = classify_document(doc)
        assert profiles[0].page_type == PageType.MIXED
        doc.close()


# ---------------------------------------------------------------- L1 抽取

@pytest.mark.unit
class TestNativeExtractor:
    def test_blocks_have_bbox(self, tmp_path):
        pdf = tmp_path / "bbox.pdf"
        _make_pdf(pdf, [[("第一段内容", 72, 100, 12), ("第二段内容", 72, 200, 12)]])
        doc = fitz.open(str(pdf))
        profiles = classify_document(doc)
        pages = extract_document(doc, profiles)
        text_blocks = [b for b in pages[0].blocks if b.kind == "text"]
        assert len(text_blocks) >= 2
        assert all(b.bbox[1] > 0 for b in text_blocks)
        assert all(b.page_no == 1 for b in text_blocks)
        doc.close()


# ---------------------------------------------------------------- L2 页眉页脚

@pytest.mark.unit
class TestHeaderFooterFilter:
    def _page(self, page_no, blocks):
        p = PageContent(page_no=page_no, page_type=PageType.NATIVE, page_height=800)
        from app.parsers.pdf.models import Block
        p.blocks = [Block(kind="text", bbox=b[:4], text=b[4], page_no=page_no) for b in blocks]
        return p

    def test_repeated_header_removed(self):
        pages = [
            self._page(i, [
                ((50, 20, 300, 40, "XX 公司机密文件")),      # 页眉
                ((50, 100, 300, 300, f"第 {i} 页的正文内容，各不相同。")),
                ((50, 760, 300, 780, f"- {i} -")),           # 页脚
            ])
            for i in range(1, 5)
        ]
        removed = filter_header_footer(pages)
        assert removed >= 8  # 4 页眉 + 4 页脚
        for p in pages:
            texts = [b.text for b in p.blocks]
            assert all("机密" not in t and not t.startswith("- ") for t in texts)
            assert any("正文" in t for t in texts)

    def test_unique_top_text_kept(self):
        pages = [
            self._page(1, [((50, 20, 300, 40, "只出现一次的标题")),
                           ((50, 100, 300, 300, "正文一"))]),
            self._page(2, [((50, 20, 300, 40, "另一个不同的标题")),
                           ((50, 100, 300, 300, "正文二"))]),
        ]
        removed = filter_header_footer(pages)
        assert removed == 0
        assert len(pages[0].blocks) == 2


# ---------------------------------------------------------------- L2 多栏

@pytest.mark.unit
class TestColumnReorder:
    def test_two_column_reading_order(self):
        from app.parsers.pdf.models import Block
        p = PageContent(page_no=1, page_type=PageType.NATIVE, page_height=800)
        # 左栏两块 + 右栏两块，插入顺序故意打乱
        p.blocks = [
            Block(kind="text", bbox=(60, 100, 260, 130), text="左栏第一段", page_no=1),
            Block(kind="text", bbox=(320, 100, 520, 130), text="右栏第一段", page_no=1),
            Block(kind="text", bbox=(60, 200, 260, 230), text="左栏第二段", page_no=1),
            Block(kind="text", bbox=(320, 200, 520, 230), text="右栏第二段", page_no=1),
        ]
        reorder_columns(p)
        texts = [b.text for b in p.blocks if b.kind == "text"]
        assert texts == ["左栏第一段", "左栏第二段", "右栏第一段", "右栏第二段"]


# ---------------------------------------------------------------- L2 标题/条款

@pytest.mark.unit
class TestHeadingAndClause:
    @pytest.mark.parametrize("text,expected", [
        ("十二", 12),
        ("3", 3),
        ("二十五", 25),
        ("一百零三", 103),
    ])
    def test_cn_to_int(self, text, expected):
        assert _cn_to_int(text) == expected

    @pytest.mark.parametrize("text,expected", [
        ("第十二条 乙方应在每月 5 日前支付费用。", "第12条"),
        ("第 3 条 甲方权利义务", "第3条"),
        ("普通段落没有条款号。", None),
    ])
    def test_normalize_clause_no(self, text, expected):
        assert normalize_clause_no(text) == expected

    def test_bookmark_toc_drives_section_path(self, tmp_path):
        pdf = tmp_path / "toc.pdf"
        _make_pdf(
            pdf,
            [
                [("第一章 总则", 72, 72, 18), ("本章规定基本原则。", 72, 120, 12)],
                [("第二章 考勤", 72, 72, 18), ("迟到三次以内每次扣款 50 元。", 72, 120, 12)],
            ],
            toc=[[1, "第一章 总则", 1], [1, "第二章 考勤", 2]],
        )
        structure = PDFParser().parse_structured(str(pdf))
        assert len(structure.toc) == 2
        paras = [n for n in structure.nodes if n.kind == "paragraph"]
        assert paras[0].section_path == ["第一章 总则"]
        assert paras[1].section_path == ["第二章 考勤"]
        assert paras[1].page_start == 2

    def test_heuristic_heading_without_toc(self, tmp_path):
        pdf = tmp_path / "heuristic.pdf"
        _make_pdf(pdf, [[
            ("第一章 总则", 72, 72, 16),
            ("第一条 本公司员工均应遵守本制度。", 72, 120, 12),
            ("第二条 考勤时间为朝九晚六。", 72, 160, 12),
        ]])
        structure = PDFParser().parse_structured(str(pdf))
        paras = [n for n in structure.nodes if n.kind == "paragraph"]
        # 第一章 被识别为标题；两条条款段落挂在其下
        headings = [n for n in structure.nodes if n.kind == "heading"]
        assert any("第一章" in h.text for h in headings)
        assert paras[0].clause_no == "第1条"
        assert paras[0].section_path[-1].startswith("第一章") or \
            any("第一章" in p for p in paras[0].section_path)


# ---------------------------------------------------------------- L3 语义切片

@pytest.mark.unit
class TestSemanticChunker:
    def _contract_pdf(self, tmp_path):
        pdf = tmp_path / "contract.pdf"
        _make_pdf(pdf, [
            [("第一章 总则", 72, 72, 16),
             ("第一条 为明确双方权利义务，特订立本合同。", 72, 120, 12),
             ("第二条 本合同自签字盖章之日起生效。", 72, 160, 12)],
            [("第二章 违约责任", 72, 72, 16),
             ("第十二条 乙方逾期交付的，每日按万分之五支付违约金。", 72, 120, 12)],
        ], toc=[[1, "第一章 总则", 1], [1, "第二章 违约责任", 2]])
        return pdf

    def test_chunks_carry_section_and_page(self, tmp_path):
        pdf = self._contract_pdf(tmp_path)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker().split(structure)
        assert chunks, "应产出 chunk"
        ch2 = [c for c in chunks if "违约金" in c.text]
        assert len(ch2) == 1
        c = ch2[0]
        assert c.page_start == 2                       # 第几页
        assert any("第二章" in s for s in c.section_path)  # 第几章
        assert c.clause_no == "第12条"                  # 第几条
        assert c.kind == "clause"

    def test_chunk_does_not_cross_sections(self, tmp_path):
        pdf = self._contract_pdf(tmp_path)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker().split(structure)
        for c in chunks:
            # 一个 chunk 内不应同时出现两章的正文
            assert not ("第一条" in c.text and "第十二条" in c.text)

    def test_section_prefix_prepended(self, tmp_path):
        pdf = self._contract_pdf(tmp_path)
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker().split(structure)
        clause_chunk = [c for c in chunks if "违约金" in c.text][0]
        assert clause_chunk.text.startswith("第二章 违约责任")

    def test_oversized_group_split_at_paragraph_boundary(self, tmp_path):
        pdf = tmp_path / "long.pdf"
        long_para = "这是一个很长的段落，用来测试超限切分。" * 60
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "第一章 总则", fontsize=16, fontname="china-s")
        # insert_textbox 才会换行，insert_text 会被页宽截断
        page.insert_textbox(fitz.Rect(72, 100, 540, 700), long_para,
                            fontsize=12, fontname="china-s")
        page.insert_text((72, 720), "第二条 短条款。", fontsize=12, fontname="china-s")
        doc.set_toc([[1, "第一章 总则", 1]])
        doc.save(str(pdf))
        doc.close()
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker(chunk_size=500).split(structure)
        assert len(chunks) >= 2
        assert all("第一章" in c.text for c in chunks)

    def test_figure_generates_summary_chunk(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        _make_scanned_pdf(pdf)  # 复用：整页图 + 无文字 → figure 占位
        structure = PDFParser().parse_structured(str(pdf))
        chunks = SemanticChunker().split(structure)
        fig_chunks = [c for c in chunks if c.kind == "figure_summary"]
        assert fig_chunks, "图像页应生成图表摘要占位 chunk"
        assert "第 1 页" in fig_chunks[0].text


# ---------------------------------------------------------------- 端到端

@pytest.mark.unit
class TestStructuredParseEndToEnd:
    def test_plain_text_compat(self, tmp_path):
        """parse() 旧接口行为不变"""
        pdf = tmp_path / "compat.pdf"
        _make_pdf(pdf, [[("兼容性测试内容", 72, 72, 12)]])
        text = PDFParser().parse(str(pdf))
        assert "兼容性测试内容" in text

    def test_scanned_pdf_warns_but_not_crash(self, tmp_path):
        pdf = tmp_path / "scan.pdf"
        _make_scanned_pdf(pdf)
        structure = PDFParser().parse_structured(str(pdf))
        assert structure.page_types[1] == PageType.SCANNED
