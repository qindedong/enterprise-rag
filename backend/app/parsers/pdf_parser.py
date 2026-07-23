"""
PDF 文档解析器

使用 PyMuPDF 提取 PDF 文字内容。
"""

from pathlib import Path

from app.core.logger import get_logger
from app.parsers.base import BaseParser

logger = get_logger(__name__)


class PDFParser(BaseParser):
    """PDF 文档解析器 — 使用 PyMuPDF"""

    @property
    def supported_formats(self) -> list[str]:
        return ["application/pdf"]

    def parse(self, file_path: str | Path) -> str:
        """
        解析 PDF 文件，提取所有页面的文字内容

        处理策略:
        - 正常的文字层 PDF: 直接提取
        - 扫描件 PDF (无文字层): 返回空字符串 + 日志告警 (v1.0 无 OCR)
        - 加密 PDF: 抛出 ValueError

        Args:
            file_path: PDF 文件路径

        Returns:
            提取的文字内容（每页以换行分隔）

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件损坏或加密
        """
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

        texts: list[str] = []
        for page in doc:
            text = page.get_text()
            if text.strip():
                texts.append(text.strip())

        doc.close()

        if not texts:
            logger.warning(f"PDF 未提取到文字内容，可能是扫描件: {path.name}")

        return "\n\n".join(texts)
