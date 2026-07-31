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
    kind: str = "paragraph"          # paragraph | clause | table | figure_summary
    clause_no: str | None = None
    table_id: str | None = None
    context_prefix: str | None = None  # Contextual Retrieval 注入的语义说明（P2）
    token_count: int = 0

    @property
    def section_title(self) -> str | None:
        return self.section_path[-1] if self.section_path else None


class SemanticChunker:
    """PDF 语义切片器"""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100):
        self.chunk_size = chunk_size
        # 二次切分仍复用成熟的递归切分器（其合法区间 500~800，做钳制）
        self._fallback = TextSplitter(
            chunk_size=max(500, min(chunk_size, 800)), chunk_overlap=chunk_overlap
        )

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
            # figure / table 节点独立成组
            if node.kind in ("figure", "table"):
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

    # ---- 条款单元：以"第X条"为边界，绝不从条款中间断 -----------------
    @staticmethod
    def _clause_units(group: list[StructNode]) -> list[list[StructNode]]:
        """把段落组切成条款单元：条款段开启新单元，普通段落挂到当前单元"""
        units: list[list[StructNode]] = []
        current: list[StructNode] = []
        for node in group:
            if node.clause_no:
                if current:
                    units.append(current)
                current = [node]
            else:
                current.append(node)
        if current:
            units.append(current)
        return units

    def _unit_chunk(self, unit: list[StructNode], section_prefix: str,
                    page_start: int, page_end: int) -> list[StructuredChunk]:
        """单个条款单元 → chunk（单元自身超限时才按段落/句边界二次切）"""
        clause_nos = [n.clause_no for n in unit if n.clause_no]
        kind = "clause" if clause_nos else "paragraph"
        body = "\n".join(n.text for n in unit)
        text = f"{section_prefix}\n{body}" if section_prefix else body

        if self._tokens(text) <= self.chunk_size:
            return [StructuredChunk(
                text=text, page_start=page_start, page_end=page_end,
                section_path=list(unit[0].section_path), kind=kind,
                clause_no=clause_nos[0] if clause_nos else None,
            )]

        # 单元超限：段落边界二次切，切不开了才用递归切分器保底
        chunks: list[StructuredChunk] = []
        buf: list[StructNode] = []
        buf_tokens = self._tokens(section_prefix) if section_prefix else 0

        def flush_buf():
            if not buf:
                return
            text_body = "\n".join(n.text for n in buf)
            t = f"{section_prefix}\n{text_body}" if section_prefix else text_body
            nos = [n.clause_no for n in buf if n.clause_no]
            chunks.append(StructuredChunk(
                text=t,
                page_start=min(n.page_start for n in buf),
                page_end=max(n.page_end for n in buf),
                section_path=list(unit[0].section_path),
                kind="clause" if nos else "paragraph",
                clause_no=nos[0] if nos else None,
            ))

        for node in unit:
            t = self._tokens(node.text)
            if t > self.chunk_size:
                flush_buf()
                buf = []
                buf_tokens = self._tokens(section_prefix) if section_prefix else 0
                for piece in self._fallback.split(node.text).chunks:
                    pt = f"{section_prefix}\n{piece}" if section_prefix else piece
                    chunks.append(StructuredChunk(
                        text=pt,
                        page_start=node.page_start, page_end=node.page_end,
                        section_path=list(unit[0].section_path), kind=kind,
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

    # ---- 表格 chunk：结构化渲染，长表按行分组且每组重复表头 ------------
    def _table_chunks(self, node: StructNode) -> list[StructuredChunk]:
        t = node.table
        section_prefix = " / ".join(node.section_path)
        page_range = (
            f"第 {node.page_start} 页" if node.page_start == node.page_end
            else f"第 {node.page_start}-{node.page_end} 页"
        )
        location = f"[{section_prefix}，{page_range}]" if section_prefix else f"[{page_range}]"

        full_text = f"{location}\n{t.to_text()}"
        if self._tokens(full_text) <= self.chunk_size:
            return [StructuredChunk(
                text=full_text, page_start=node.page_start, page_end=node.page_end,
                section_path=list(node.section_path), kind="table",
                table_id=t.table_id,
            )]

        # 长表：按行贪心分组，每组重复位置标注 + 表头
        header_lines = []
        if t.caption:
            header_lines.append(f"表格：{t.caption}")
        if t.headers:
            header_lines.append("表头：" + " | ".join(t.headers))
        header_text = "\n".join([location, *header_lines])
        header_tokens = self._tokens(header_text)

        chunks: list[StructuredChunk] = []
        buf: list[list[str]] = []
        buf_tokens = header_tokens
        for row in t.rows:
            row_text = "，".join(
                f"{h}={v}" for h, v in zip(t.headers, row) if v
            ) if t.headers and len(row) == len(t.headers) else " | ".join(c for c in row if c)
            rt = self._tokens(row_text) + 8  # "行 N：" 前缀余量
            if buf and buf_tokens + rt > self.chunk_size:
                body = "\n".join(
                    f"行 {i}：" + (
                        "，".join(f"{h}={v}" for h, v in zip(t.headers, r) if v)
                        if t.headers and len(r) == len(t.headers)
                        else " | ".join(c for c in r if c)
                    )
                    for i, r in enumerate(buf, 1)
                )
                chunks.append(StructuredChunk(
                    text=f"{header_text}\n{body}",
                    page_start=node.page_start, page_end=node.page_end,
                    section_path=list(node.section_path), kind="table",
                    table_id=t.table_id,
                ))
                buf = []
                buf_tokens = header_tokens
            buf.append(row)
            buf_tokens += rt
        if buf:
            body = "\n".join(
                f"行 {i}：" + (
                    "，".join(f"{h}={v}" for h, v in zip(t.headers, r) if v)
                    if t.headers and len(r) == len(t.headers)
                    else " | ".join(c for c in r if c)
                )
                for i, r in enumerate(buf, 1)
            )
            chunks.append(StructuredChunk(
                text=f"{header_text}\n{body}",
                page_start=node.page_start, page_end=node.page_end,
                section_path=list(node.section_path), kind="table",
                table_id=t.table_id,
            ))
        return chunks

    # ---- 输出：组 → 一个或多个 chunk --------------------------------
    def _emit_group(self, group: list[StructNode]) -> list[StructuredChunk]:
        first = group[0]

        # 表格节点：结构化渲染
        if first.kind == "table" and first.table:
            return self._table_chunks(first)

        # 图表摘要 chunk：P3 视觉理解已生成描述时携带真实内容，否则占位
        if first.kind == "figure":
            page_range = (
                f"第 {first.page_start} 页" if first.page_start == first.page_end
                else f"第 {first.page_start}-{first.page_end} 页"
            )
            section = " / ".join(first.section_path) or "未分章节"
            header = f"[图片/图表：{section}，{page_range}]"
            text = f"{header}\n{first.text}" if first.text.strip() else header
            return [StructuredChunk(
                text=text,
                page_start=first.page_start, page_end=first.page_end,
                section_path=list(first.section_path), kind="figure_summary",
            )]

        section_prefix = " / ".join(first.section_path)
        prefix_tokens = self._tokens(section_prefix) if section_prefix else 0

        # 条款单元装箱：合并在条款边界处发生，绝不从条款中间断
        units = self._clause_units(group)
        chunks: list[StructuredChunk] = []
        buf: list[StructNode] = []
        buf_tokens = prefix_tokens

        def flush_buf():
            if not buf:
                return
            nos = [n.clause_no for n in buf if n.clause_no]
            body = "\n".join(n.text for n in buf)
            text = f"{section_prefix}\n{body}" if section_prefix else body
            chunks.append(StructuredChunk(
                text=text,
                page_start=min(n.page_start for n in buf),
                page_end=max(n.page_end for n in buf),
                section_path=list(first.section_path),
                kind="clause" if nos else "paragraph",
                # 只有单条款 chunk 才标注条款号，避免歧义
                clause_no=nos[0] if len(set(nos)) == 1 else None,
            ))

        for unit in units:
            unit_text = "\n".join(n.text for n in unit)
            ut = self._tokens(unit_text)
            if prefix_tokens + ut > self.chunk_size:
                # 单元自身超限：独立走二次切分
                flush_buf()
                buf = []
                buf_tokens = prefix_tokens
                chunks.extend(self._unit_chunk(
                    unit, section_prefix,
                    min(n.page_start for n in unit),
                    max(n.page_end for n in unit),
                ))
                continue
            if buf and buf_tokens + ut > self.chunk_size:
                flush_buf()
                buf = []
                buf_tokens = prefix_tokens
            buf.extend(unit)
            buf_tokens += ut
        flush_buf()
        return chunks
