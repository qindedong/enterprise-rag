"""
解析器注册中心

根据文件 MIME 类型自动选择合适的解析器。
"""

from typing import ClassVar

from app.core.logger import get_logger
from app.parsers.base import BaseParser
from app.parsers.markdown_parser import MarkdownParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.text_parser import TextParser

logger = get_logger(__name__)


class ParserRegistry:
    """解析器注册中心 — 根据文件类型匹配解析器"""

    # MIME 类型 → 解析器实例
    _parsers: ClassVar[dict[str, BaseParser]] = {}

    @classmethod
    def initialize(cls) -> None:
        """注册所有解析器"""
        parsers = [PDFParser(), MarkdownParser(), TextParser()]
        for parser in parsers:
            for fmt in parser.supported_formats:
                cls._parsers[fmt] = parser
        logger.info(f"解析器注册完成: {list(cls._parsers.keys())}")

    @classmethod
    def get_parser(cls, mime_type: str) -> BaseParser:
        """
        根据 MIME 类型获取解析器

        Args:
            mime_type: 文件的 MIME 类型

        Returns:
            对应的解析器实例

        Raises:
            ValueError: 不支持的 MIME 类型
        """
        if not cls._parsers:
            cls.initialize()

        parser = cls._parsers.get(mime_type)
        if not parser:
            supported = list(cls._parsers.keys())
            raise ValueError(f"不支持的文件类型: {mime_type}。支持的类型: {supported}")
        return parser

    @classmethod
    def is_supported(cls, mime_type: str) -> bool:
        """检查是否支持该 MIME 类型"""
        if not cls._parsers:
            cls.initialize()
        return mime_type in cls._parsers
