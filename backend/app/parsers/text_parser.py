"""
纯文本解析器
"""

from pathlib import Path

from app.parsers.base import BaseParser


class TextParser(BaseParser):
    """纯文本解析器 — 支持 UTF-8 / GBK 编码"""

    @property
    def supported_formats(self) -> list[str]:
        return ["text/plain"]

    def parse(self, file_path: str | Path) -> str:
        """读取纯文本文件，自动检测编码"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 尝试多种编码
        for encoding in ["utf-8", "gbk", "gb2312", "latin-1"]:
            try:
                with open(path, "r", encoding=encoding) as f:
                    content = f.read()
                if content.strip():
                    return content
            except (UnicodeDecodeError, UnicodeError):
                continue

        raise ValueError("无法识别文件编码，支持 UTF-8 / GBK / GB2312")
