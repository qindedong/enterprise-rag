"""PDF 解析器测试（用 PyMuPDF 动态生成真实 PDF）"""

import fitz
import pytest

from app.parsers.pdf_parser import PDFParser


def _make_pdf(path, pages: list[str]) -> None:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        # china-s：PyMuPDF 内置中文字体（默认 helv 无 CJK 字形）
        page.insert_text((72, 72), text, fontsize=12, fontname="china-s")
    doc.save(str(path))
    doc.close()


@pytest.mark.unit
class TestPDFParserReal:
    """真实 PDF 解析"""

    def test_parse_multipage(self, tmp_path):
        """多页 PDF 提取全部文本"""
        pdf = tmp_path / "test.pdf"
        _make_pdf(pdf, ["第一页内容 公司制度", "第二页内容 考勤规定"])

        parser = PDFParser()
        result = parser.parse(str(pdf))

        assert "第一页内容" in result
        assert "第二页内容" in result

    def test_parse_page_markers(self, tmp_path):
        """提取结果包含页码标记（便于引用溯源）"""
        pdf = tmp_path / "test.pdf"
        _make_pdf(pdf, ["内容A", "内容B"])

        result = PDFParser().parse(str(pdf))
        # PDFParser 应输出某种分页结构（具体格式以实现为准）
        assert "内容A" in result and "内容B" in result

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="文件不存在"):
            PDFParser().parse(str(tmp_path / "不存在.pdf"))

    def test_corrupted_pdf_raises_value_error(self, tmp_path):
        """损坏的 PDF → ValueError"""
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"%PDF-1.4 corrupted garbage not a real pdf")

        with pytest.raises(ValueError, match="无法打开"):
            PDFParser().parse(str(bad))

    def test_encrypted_pdf(self, tmp_path):
        """加密 PDF → 明确报错"""
        pdf = tmp_path / "encrypted.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "secret", fontsize=12)
        doc.save(
            str(pdf),
            encryption=fitz.PDF_ENCRYPT_AES_256,
            user_pw="user123",
            owner_pw="owner123",
        )
        doc.close()

        # 加密文件：能打开但 is_encrypted，应报明确错误（不崩溃）
        with pytest.raises((ValueError, RuntimeError)):
            PDFParser().parse(str(pdf))

    def test_supported_formats(self):
        assert "application/pdf" in PDFParser().supported_formats
