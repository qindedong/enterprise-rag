"""
Markdown 文档解析器
"""

from pathlib import Path

from app.parsers.base import BaseParser


class MarkdownParser(BaseParser):
    """Markdown 文档解析器 — 保留标题层级结构"""

    @property
    def supported_formats(self) -> list[str]:
        return ["text/markdown", "text/x-markdown", "text/md"]

    def parse(self, file_path: str | Path) -> str:
        """读取 Markdown 文件内容（不修改原始格式）"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if not content.strip():
            raise ValueError("文件内容为空")

        return content
