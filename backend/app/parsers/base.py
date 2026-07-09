"""
文档解析器 — 抽象接口

所有文档解析器必须实现 parse() 方法。
通过 ParserRegistry 根据文件类型选择合适的解析器。
"""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    """文档解析器抽象基类

    所有格式解析器必须继承此类并实现 parse() 方法。
    """

    @abstractmethod
    def parse(self, file_path: str | Path) -> str:
        """
        解析文档并提取文本内容

        Args:
            file_path: 文档文件路径

        Returns:
            提取的纯文本内容

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式不支持或内容损坏
        """
        ...

    @property
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """返回支持的 MIME 类型列表"""
        ...
