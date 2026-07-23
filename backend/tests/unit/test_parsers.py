"""文档解析与分块模块单元测试"""

import os
import tempfile

import pytest

from app.parsers.markdown_parser import MarkdownParser
from app.parsers.text_parser import TextParser
from app.utils.text_splitter import TextSplitter


class TestMarkdownParser:
    """Markdown 解析器测试"""

    def test_parse_markdown_file(self):
        """测试：解析 Markdown 文件"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write("# 测试标题\n\n## 第一节\n内容段落\n\n## 第二节\n另一段内容")
        tmp.close()

        try:
            parser = MarkdownParser()
            content = parser.parse(tmp.name)
            assert "测试标题" in content
            assert "第一节" in content
            assert "第二节" in content
        finally:
            os.unlink(tmp.name)

    def test_parse_empty_file_raises(self):
        """测试：空文件抛出 ValueError"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8")
        tmp.write("")
        tmp.close()

        try:
            parser = MarkdownParser()
            with pytest.raises(ValueError):
                parser.parse(tmp.name)
        finally:
            os.unlink(tmp.name)

    def test_parse_nonexistent_file_raises(self):
        """测试：不存在的文件抛出 FileNotFoundError"""
        parser = MarkdownParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.md")


class TestTextParser:
    """纯文本解析器测试"""

    def test_parse_utf8(self):
        """测试：UTF-8 编码解析"""
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8")
        tmp.write("这是一段中文测试内容\n第二行内容")
        tmp.close()

        try:
            parser = TextParser()
            content = parser.parse(tmp.name)
            assert "中文测试" in content
            assert "第二行" in content
        finally:
            os.unlink(tmp.name)


class TestTextSplitter:
    """文本分块器测试"""

    def test_split_produces_chunks(self):
        """测试：正常分块"""
        splitter = TextSplitter(chunk_size=500, chunk_overlap=100)
        text = "这是一段测试文本。包含多个句子。" * 50
        result = splitter.split(text)

        assert result.total_chunks > 0
        assert len(result.chunks) == result.total_chunks
        assert len(result.token_counts) == result.total_chunks

    def test_split_empty_text(self):
        """测试：空文本返回空列表"""
        splitter = TextSplitter()
        result = splitter.split("")

        assert result.total_chunks == 0
        assert result.chunks == []

    def test_split_short_text(self):
        """测试：短文本不拆分"""
        splitter = TextSplitter(chunk_size=500, chunk_overlap=100)
        result = splitter.split("短短一句话。")

        assert result.total_chunks >= 1
        assert result.chunks[0] == "短短一句话。"

    def test_splitter_validates_chunk_size(self):
        """测试：分块大小范围校验"""
        # chunk_size < 500 应该抛出 ValueError
        with pytest.raises(ValueError):
            TextSplitter(chunk_size=100)

        # chunk_size > 800 应该抛出 ValueError
        with pytest.raises(ValueError):
            TextSplitter(chunk_size=1000)

    def test_default_splitter(self):
        """测试：默认分块器参数正确"""
        from app.utils.text_splitter import create_default_splitter

        splitter = create_default_splitter()
        assert splitter.chunk_size == 500
        assert splitter.chunk_overlap == 100
