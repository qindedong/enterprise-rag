"""
文本分块器

使用 LangChain 的 RecursiveCharacterTextSplitter 实现智能分块。
硬性标准：chunk_size=500, chunk_overlap=100（可通过配置调整 500~800）
"""

from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkResult:
    """分块结果"""
    chunks: list[str]
    token_counts: list[int]
    total_chunks: int


class TextSplitter:
    """文本分块器 — 递归字符分割

    分隔符优先级：Markdown标题 → 段落换行 → 句号 → 空格
    """

    # 标准分隔符（按优先级排序）
    DEFAULT_SEPARATORS: list[str] = [
        "\n## ",       # Markdown H2
        "\n### ",      # Markdown H3
        "\n#### ",     # Markdown H4
        "\n",          # 段落换行
        "。",          # 中文句号
        ". ",          # 英文句号
        "；",          # 中文分号
        "; ",          # 英文分号
        " ",           # 空格（最后手段）
    ]

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        """
        Args:
            chunk_size: 分块大小（Token 数），范围 500~800
            chunk_overlap: 重叠大小（Token 数），固定 100
        """
        if chunk_size < 500 or chunk_size > 800:
            raise ValueError(f"chunk_size 必须在 500~800 之间，当前值: {chunk_size}")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 初始化 LangChain 分块器
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=self.DEFAULT_SEPARATORS,
            length_function=self._token_count,
            is_separator_regex=False,
        )

    def split(self, text: str) -> ChunkResult:
        """
        将文本切分为多个语义片段

        Args:
            text: 待分块的文本内容

        Returns:
            ChunkResult 包含分块列表和 Token 计数
        """
        if not text or not text.strip():
            logger.warning("输入文本为空，返回空分块列表")
            return ChunkResult(chunks=[], token_counts=[], total_chunks=0)

        # 使用 LangChain 分块
        try:
            chunks = self._splitter.split_text(text)
        except Exception as e:
            logger.error(f"分块过程异常: {e}，回退到简单分段")
            chunks = [text]

        # 验证和过滤
        chunks = self._validate_chunks(chunks)
        token_counts = [self._token_count(c) for c in chunks]

        logger.info(
            f"分块完成: 文本长度={len(text)} → {len(chunks)} 个分块, "
            f"平均 Token 数={sum(token_counts)//max(len(token_counts), 1)}"
        )

        return ChunkResult(chunks=chunks, token_counts=token_counts, total_chunks=len(chunks))

    def _validate_chunks(self, chunks: list[str]) -> list[str]:
        """分块质量校验"""
        validated = []
        for i, chunk in enumerate(chunks):
            token_count = self._token_count(chunk)

            # 空分块过滤
            if token_count == 0:
                logger.warning(f"发现空分块 (index={i})，已跳过")
                continue

            # 过长分块告警（不丢弃，避免数据丢失）
            if token_count > 800:
                logger.warning(f"分块过长 ({token_count} tokens, index={i})，建议检查原始文档")

            validated.append(chunk)

        if len(validated) < len(chunks):
            logger.info(f"分块质量校验: {len(chunks)} → {len(validated)} 个 (过滤 {len(chunks) - len(validated)} 个)")

        return validated

    @staticmethod
    def _token_count(text: str) -> int:
        """Token 计数 — 使用 tiktoken cl100k_base 编码（兼容 text-embedding-3）"""
        try:
            import tiktoken
            encoder = tiktoken.get_encoding("cl100k_base")
            return len(encoder.encode(text))
        except Exception:
            # 回退：中文字符 ≈ 1.5 tokens，英文单词 ≈ 1.3 tokens
            import re
            chinese_chars = len(re.findall(r'[一-鿿]', text))
            english_words = len(re.findall(r'[a-zA-Z]+', text))
            return int(chinese_chars * 1.5 + english_words * 1.3)


def create_default_splitter() -> TextSplitter:
    """创建默认分块器（chunk_size=500, overlap=100）"""
    return TextSplitter(chunk_size=500, chunk_overlap=100)
