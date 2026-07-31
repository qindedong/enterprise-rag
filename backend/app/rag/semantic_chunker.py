"""L3 语义切片器 — 按文档结构切片，取代对 PDF 的固定长度硬切

规则:
    - 同一章节路径下的连续段落合并为一个 chunk（标题文本作为首行上下文）
    - 超出 chunk_size 时在段落边界二次切，绝不跨标题
    - 条款段落（第X条）的条款号写入 chunk metadata
    - figure 节点生成占位摘要行，保留页码与章节归属

每个 chunk 携带完整 metadata：页码范围、章节路径、类型、条款号。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.logger import get_logger
from app.parsers.pdf.models import DocumentStructure, StructNode
from app.utils.text_splitter import TextSplitter

logger = get_logger(__name__)


@dataclass
class StructuredChunk:
    """带结构 metadata 的分块"""

    text: str
    page_start: int
    page_end: int
    section_path: list[str] = field(default_factory=list)
    kind: str = "paragraph"          # paragraph | figure_summary | clause
    clause_no: str | None = None
    token_count: int = 0

    @property
    def section_title(self) -> str | None:
        return self.section_path[-1] if self.section_path else None


class SemanticChunker:
    """PDF 语义切片器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        # 二次切分仍复用成熟的递归切分器
        self._fallback = TextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    @staticmethod
    def _tokens(text: str) -> int:
        return TextSplitter._token_count(text)

    def split(self, structure: DocumentStructure) -> list[StructuredChunk]:
        """将 DocumentStructure 切为 StructuredChunk 列表"""
        groups = self._group_nodes(structure.nodes)
        chunks: list[StructuredChunk] = []
        for group in groups:
            chunks.extend(self._emit_group(group))
        for c in chunks:
            c.token_count = self._tokens(c.text)
        logger.info(
            f"语义切片完成: {len(structure.nodes)} 个节点 → {len(chunks)} 个 chunk"
        )
        return chunks

    # ---- 分组：同章节路径的连续段落/条款归为一组 ---------------------
    @staticmethod
    def _group_nodes(nodes: list[StructNode]) -> list[list[StructNode]]:
        groups: list[list[StructNode]] = []
        current: list[StructNode] = []
        current_key: tuple | None = None

        def flush():
            nonlocal current
            if current:
                groups.append(current)
                current = []

        for node in nodes:
            if node.kind == "heading":
                flush()
                continue  # 标题本身不单独成组，作为后续段落的前缀
            # figure 节点独立成组（生成图表摘要占位）
            if node.kind == "figure":
                flush()
                groups.append([node])
                continue
            key = tuple(node.section_path)
            if current_key is not None and key != current_key:
                flush()
            current_key = key
            current.append(node)
        flush()
        return groups

    # ---- 输出：组 → 一个或多个 chunk --------------------------------
    def _emit_group(self, group: list[StructNode]) -> list[StructuredChunk]:
        first = group[0]

        # 图表摘要占位 chunk（视觉理解为 P3，先保留可检索占位）
        if first.kind == "figure":
            page_range = (
                f"第 {first.page_start} 页" if first.page_start == first.page_end
                else f"第 {first.page_start}-{first.page_end} 页"
            )
            section = " / ".join(first.section_path) or "未分章节"
            return [StructuredChunk(
                text=f"[图片/图表：{section}，{page_range}]",
                page_start=first.page_start, page_end=first.page_end,
                section_path=list(first.section_path), kind="figure_summary",
            )]

        section_prefix = " / ".join(first.section_path)
        texts = [n.text for n in group]
        body = "\n".join(texts)
        full = f"{section_prefix}\n{body}" if section_prefix else body

        page_start = min(n.page_start for n in group)
        page_end = max(n.page_end for n in group)
        clause_nos = [n.clause_no for n in group if n.clause_no]
        kind = "clause" if clause_nos else "paragraph"

        # 未超限：整组一个 chunk
        if self._tokens(full) <= self.chunk_size:
            return [StructuredChunk(
                text=full, page_start=page_start, page_end=page_end,
                section_path=list(first.section_path), kind=kind,
                clause_no=clause_nos[0] if len(clause_nos) == 1 else None,
            )]

        # 超限：在段落边界贪心装箱，每箱重复章节前缀
        chunks: list[StructuredChunk] = []
        buf: list[StructNode] = []
        buf_tokens = self._tokens(section_prefix) if section_prefix else 0

        def flush_buf():
            if not buf:
                return
            text_body = "\n".join(n.text for n in buf)
            text = f"{section_prefix}\n{text_body}" if section_prefix else text_body
            nos = [n.clause_no for n in buf if n.clause_no]
            chunks.append(StructuredChunk(
                text=text,
                page_start=min(n.page_start for n in buf),
                page_end=max(n.page_end for n in buf),
                section_path=list(first.section_path),
                kind="clause" if nos else "paragraph",
                clause_no=nos[0] if len(nos) == 1 else None,
            ))

        for node in group:
            t = self._tokens(node.text)
            # 单个段落就超限 → 用递归切分器硬切该段落
            if t > self.chunk_size:
                flush_buf()
                buf = []
                buf_tokens = self._tokens(section_prefix) if section_prefix else 0
                for piece in self._fallback.split(node.text).chunks:
                    text = f"{section_prefix}\n{piece}" if section_prefix else piece
                    chunks.append(StructuredChunk(
                        text=text,
                        page_start=node.page_start, page_end=node.page_end,
                        section_path=list(first.section_path), kind=kind,
                        clause_no=node.clause_no,
                    ))
                continue
            if buf and buf_tokens + t > self.chunk_size:
                flush_buf()
                buf = []
                buf_tokens = self._tokens(section_prefix) if section_prefix else 0
            buf.append(node)
            buf_tokens += t
        flush_buf()
        return chunks
