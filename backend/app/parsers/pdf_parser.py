"""
PDF 文档解析器

L1/L2 门面：编排 页面分类 → 块级抽取 → 结构还原。
- ``parse()``           保持 BaseParser 接口，返回纯文本（向后兼容）
- ``parse_structured()`` 返回 DocumentStructure（页码/章节/条款/块坐标）
"""

from pathlib import Path

from app.core.logger import get_logger
from app.parsers.base import BaseParser
from app.parsers.pdf.models import DocumentStructure

logger = get_logger(__name__)


class PDFParser(BaseParser):
    """PDF 文档解析器 — 使用 PyMuPDF"""

    @property
    def supported_formats(self) -> list[str]:
        return ["application/pdf"]

    def _open(self, file_path: str | Path):
        """打开并校验 PDF，返回 fitz.Document"""
        import fitz  # PyMuPDF

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        try:
            doc = fitz.open(str(path))
        except Exception as e:
            raise ValueError(f"PDF 文件无法打开，可能已损坏: {e}") from e

        if doc.is_encrypted:
            doc.close()
            raise ValueError("PDF 文件已加密，无法解析")
        return doc

    def parse(self, file_path: str | Path) -> str:
        """
        解析 PDF 文件，提取所有页面的文字内容

        处理策略:
        - 正常的文字层 PDF: 直接提取
        - 扫描件 PDF (无文字层): 返回空字符串 + 日志告警 (OCR 为 P2)
        - 加密 PDF: 抛出 ValueError

        Returns:
            提取的文字内容（每页以换行分隔）

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件损坏或加密
        """
        doc = self._open(file_path)
        texts: list[str] = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                texts.append(text.strip())
        doc.close()

        if not texts:
            logger.warning(f"PDF 未提取到文字内容，可能是扫描件: {Path(file_path).name}")

        return "\n\n".join(texts)

    def parse_structured(self, file_path: str | Path) -> DocumentStructure:
        """结构化解析：L1 分类抽取 → L2 结构还原

        Returns:
            DocumentStructure（目录、结构节点流、每页类型）

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件损坏或加密
        """
        from app.parsers.pdf.classifier import classify_document
        from app.parsers.pdf.native_extractor import extract_document
        from app.parsers.pdf.structure import build_structure

        doc = self._open(file_path)
        try:
            # L1: 页面分类 + 块级抽取
            profiles = classify_document(doc)
            pages = extract_document(doc, profiles)
            # L2: 结构还原
            structure = build_structure(
                doc, pages, str(file_path),
                page_types={p.page_no: p.page_type for p in profiles},
            )
        finally:
            doc.close()
        return structure
