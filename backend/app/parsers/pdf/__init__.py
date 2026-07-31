"""PDF 结构化处理子包（四层架构 L1/L2）

模块:
    classifier        — L1 页面分类（原生 / 扫描 / 图文混排）
    native_extractor  — L1 原生块级抽取（带 bbox 坐标）
    structure         — L2 结构还原（页眉页脚过滤 / 多栏重组 / 标题层级 / 条款）

设计文档: docs/pdf_pipeline_architecture.md
"""

from app.parsers.pdf.models import (
    Block,
    DocumentStructure,
    PageContent,
    PageProfile,
    PageType,
    StructNode,
    TocNode,
)

__all__ = [
    "Block",
    "DocumentStructure",
    "PageContent",
    "PageProfile",
    "PageType",
    "StructNode",
    "TocNode",
]
