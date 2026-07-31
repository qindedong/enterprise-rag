"""PDF 结构化处理 — 数据契约（L1/L2 层共享）

PDF 不是纯文本，而是带坐标的结构化版面。L1/L2 各模块之间
一律用本文件的 dataclass 传递，不压扁成字符串。
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class PageType(enum.StrEnum):
    """页面类型（L1 分类结果）"""

    NATIVE = "native"    # 原生文本页：文字层正常，直接块级抽取
    SCANNED = "scanned"  # 扫描页：无/极薄文字层 + 整页大图，需 OCR（P2）
    MIXED = "mixed"      # 图文混排页：文字层正常但含显著图像区域


@dataclass
class PageProfile:
    """L1 页面分类结果"""

    page_no: int                 # 页码（从 1 开始）
    page_type: PageType
    text_length: int             # 文字层字符数
    image_coverage: float        # 图像区域占页面面积比例 0~1
    image_count: int


@dataclass
class Block:
    """L1 块级内容（带版面坐标）"""

    kind: str                    # "text" | "image"
    bbox: tuple[float, float, float, float]  # (x0, y0, x1, y1)
    text: str = ""
    page_no: int = 0             # 所属页码（从 1 开始）

    @property
    def x0(self) -> float:
        return self.bbox[0]

    @property
    def y0(self) -> float:
        return self.bbox[1]

    @property
    def x1(self) -> float:
        return self.bbox[2]

    @property
    def y1(self) -> float:
        return self.bbox[3]


@dataclass
class PageContent:
    """L1 输出：一页的块级内容"""

    page_no: int                 # 页码（从 1 开始）
    page_type: PageType
    page_height: float
    blocks: list[Block] = field(default_factory=list)
    ocr_confidence: float | None = None  # 仅 OCR 页（P2）


@dataclass
class TocNode:
    """目录节点（PDF 书签或启发式标题）"""

    level: int                   # 层级，从 1 开始
    title: str
    page_no: int                 # 指向的页码（从 1 开始；未知为 0）


@dataclass
class StructuredTable:
    """L2 结构化表格（行列 + 表头）"""

    table_id: str                          # "表 2-1" 或 "table-p8-1"
    page_no: int
    bbox: tuple[float, float, float, float]
    caption: str | None = None
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)

    def to_text(self, max_rows: int | None = None,
                header_repeat: bool = False) -> str:
        """渲染为带语义的结构化文本（供切片/检索）

        每行展开为 "列名1=值, 列名2=值" 形式，数字绑定指标与年份。
        """
        lines = []
        if self.caption:
            lines.append(f"表格：{self.caption}")
        if self.headers:
            lines.append("表头：" + " | ".join(self.headers))
        rows = self.rows if max_rows is None else self.rows[:max_rows]
        for i, row in enumerate(rows, 1):
            if self.headers and len(row) == len(self.headers):
                pairs = "，".join(
                    f"{h}={v}" for h, v in zip(self.headers, row) if v
                )
                lines.append(f"行 {i}：{pairs}")
            else:
                lines.append(f"行 {i}：" + " | ".join(c for c in row if c))
        return "\n".join(lines)


@dataclass
class StructNode:
    """L2 输出：有序结构节点"""

    kind: str                    # "heading" | "paragraph" | "table" | "figure" | "footnote"
    text: str
    page_start: int
    page_end: int
    level: int = 0               # 标题层级（非标题为 0）
    section_path: list[str] = field(default_factory=list)  # 章节路径快照
    clause_no: str | None = None  # 合同条款号，如 "第12条"
    table: StructuredTable | None = None  # kind="table" 时的结构化表格
    figure_bbox: tuple[float, float, float, float] | None = None  # kind="figure" 时的图像区域


@dataclass
class DocumentStructure:
    """L2 输出：文档结构树/节点流"""

    file_path: str
    page_count: int
    toc: list[TocNode] = field(default_factory=list)
    nodes: list[StructNode] = field(default_factory=list)
    page_types: dict[int, PageType] = field(default_factory=dict)

    def plain_text(self) -> str:
        """压扁为纯文本（向后兼容旧流程）"""
        return "\n\n".join(n.text for n in self.nodes if n.text.strip())
