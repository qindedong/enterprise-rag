"""L1 视觉理解路径 — 对 PDF 图表区域调多模态模型生成描述

P3：结构还原阶段 figure 节点只有页码占位，本模块把图像区域渲染出来，
交给视觉模型生成可检索的描述文本（趋势、对比、构成、异常点），
回填到 figure 节点的 text，让 L3 的 figure_summary chunk 携带真实内容。

设计原则与 OCR 路径一致：**失败降级不阻塞** —— 视觉模型不可用、
渲染失败、单图分析失败，都只保留占位，文档照常入库。
"""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger
from app.parsers.pdf.models import DocumentStructure, StructNode

logger = get_logger(__name__)

# 渲染分辨率：图表细节（坐标轴文字、图例）需要比正文更高的 DPI
RENDER_DPI = 200
# 单图描述长度上限，避免视觉模型长篇输出污染 chunk
MAX_DESC_CHARS = 300

_CHART_PROMPT = (
    "这是文档中的一张图片/图表。请用中文用 1-3 句话描述它的核心信息："
    "如果是图表（柱状图/折线图/饼图等），说明图表类型、对比对象、"
    "关键数值趋势或占比、异常点；如果是流程图，说明流程步骤；"
    "如果是截图或普通图片，说明画面内容。"
    f"不超过 {MAX_DESC_CHARS} 字，直接输出描述，不要加任何前缀。"
)


def _render_region(pdf_path: str, page_no: int, bbox) -> bytes | None:
    """把指定页的图像区域渲染为 PNG（bbox 为 PDF 坐标）"""
    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            page = doc[page_no - 1]
            clip = fitz.Rect(*bbox) if bbox else page.rect
            # 图像区域可能略超出页边界，裁剪到页内
            clip = clip & page.rect
            if clip.is_empty:
                return None
            zoom = RENDER_DPI / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
            return pix.tobytes("png")
    except Exception as e:
        logger.warning(f"第 {page_no} 页图像区域渲染失败: {e}")
        return None


async def analyze_figure(
    llm_client, pdf_path: str, node: StructNode
) -> str | None:
    """分析单个 figure 节点，返回描述文本（失败返回 None）"""
    img = _render_region(pdf_path, node.page_start, node.figure_bbox)
    if not img:
        return None
    section = " / ".join(node.section_path) or "未分章节"
    prompt = f"{_CHART_PROMPT}\n（该图出自文档「{section}」第 {node.page_start} 页）"
    try:
        result = await llm_client.generate_with_image(prompt, img)
        desc = (result.get("answer") or "").strip()
        if len(desc) < 4:
            return None
        return desc[:MAX_DESC_CHARS]
    except Exception as e:
        logger.warning(f"第 {node.page_start} 页图表视觉分析失败: {e}")
        return None


async def analyze_figures(
    llm_client,
    pdf_path: str,
    structure: DocumentStructure,
    concurrency: int = 3,
) -> int:
    """对整篇文档的 figure 节点批量做视觉理解，回填 node.text

    Args:
        llm_client: 具备 generate_with_image 的客户端
        pdf_path: PDF 文件路径（渲染图像区域用）
        structure: L2 结构还原结果（原地修改）
        concurrency: 并发上限，避免打爆视觉 API

    Returns:
        成功分析的图表数量
    """
    figures = [n for n in structure.nodes if n.kind == "figure"]
    if not figures:
        return 0

    sem = asyncio.Semaphore(concurrency)

    async def _one(node: StructNode) -> bool:
        async with sem:
            desc = await analyze_figure(llm_client, pdf_path, node)
            if desc:
                node.text = desc
                return True
            return False

    results = await asyncio.gather(*[_one(n) for n in figures])
    done = sum(1 for r in results if r)
    logger.info(f"视觉理解: {done}/{len(figures)} 个图表生成描述")
    return done
