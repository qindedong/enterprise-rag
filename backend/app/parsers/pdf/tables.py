"""L2 表格结构化 — 用 PyMuPDF find_tables 把表格还原为行列数据

适用：有框线或单元格对齐规整的表格（覆盖约 80% 商务文档）。
无线表、重度合并单元格的复杂表格识别率有限，由 P3 视觉模型兜底。
"""

from __future__ import annotations

import re

from app.core.logger import get_logger
from app.parsers.pdf.models import Block, StructuredTable

logger = get_logger(__name__)

# 表注模式："表 2-1 xxx" / "表3 xxx" / "Table 1 xxx"
RE_CAPTION = re.compile(r"^(表\s*[\d一二三四五六七八九十]+[-—.\d]*\s*[:：]?\s*\S|Table\s*\d+)", re.I)
CAPTION_ABOVE_MAX_DIST = 60  # 表注与表格上缘的最大距离（pt）


def _clean_cell(text: str | None) -> str:
    """清理单元格文本（去换行/多余空白）"""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.replace("\n", " ")).strip()


def extract_tables(page, page_no: int) -> list[StructuredTable]:
    """提取单页的全部表格

    Args:
        page: fitz.Page 对象
        page_no: 页码（从 1 开始）

    Returns:
        StructuredTable 列表（按纵坐标排序）
    """
    try:
        finder = page.find_tables()
    except Exception as e:
        logger.warning(f"第 {page_no} 页表格检测失败: {e}")
        return []

    tables: list[StructuredTable] = []
    for idx, tab in enumerate(finder.tables, 1):
        try:
            data = tab.extract()
        except Exception as e:
            logger.warning(f"第 {page_no} 页表格 {idx} 提取失败: {e}")
            continue
        if not data or len(data) < 2:
            continue  # 单行表大概率是误判（一条横线）

        rows = [[_clean_cell(c) for c in row] for row in data]
        # 过滤全空行
        rows = [r for r in rows if any(c for c in r)]
        if len(rows) < 2:
            continue

        headers, body = rows[0], rows[1:]
        # 表头质量检查：表头全空或与首行重复 → 无表头，全部作数据行
        if not any(headers) or headers == body[0]:
            headers, body = [], rows

        tables.append(StructuredTable(
            table_id=f"table-p{page_no}-{idx}",
            page_no=page_no,
            bbox=(tab.bbox[0], tab.bbox[1], tab.bbox[2], tab.bbox[3]),
            headers=headers,
            rows=body,
        ))

    tables.sort(key=lambda t: t.bbox[1])
    if tables:
        logger.info(
            f"第 {page_no} 页检测到 {len(tables)} 张表格"
            f"（{[f'{len(t.rows)}行' for t in tables]}）"
        )
    return tables


def block_in_table(block: Block, tables: list[StructuredTable]) -> bool:
    """判断文本块是否落在某张表格的 bbox 内（块中心点判定）"""
    cx = (block.x0 + block.x1) / 2
    cy = (block.y0 + block.y1) / 2
    for t in tables:
        x0, y0, x1, y1 = t.bbox
        if x0 <= cx <= x1 and y0 <= cy <= y1:
            return True
    return False


def find_caption(table: StructuredTable, blocks: list[Block]) -> str | None:
    """在表格上方寻找表注（"表 X-X xxx"），命中则返回文本"""
    x0, y0, x1, _y1 = table.bbox
    best: tuple[float, str] | None = None
    for blk in blocks:
        if blk.kind != "text":
            continue
        m = RE_CAPTION.match(blk.text.strip())
        if not m:
            continue
        # 只取表格上方、纵向距离在阈值内、横向有重叠的块
        dist = y0 - blk.y1
        if dist < -5 or dist > CAPTION_ABOVE_MAX_DIST:
            continue
        if blk.x1 < x0 - 20 or blk.x0 > x1 + 20:
            continue
        if best is None or dist < best[0]:
            best = (dist, blk.text.strip())
    return best[1] if best else None
