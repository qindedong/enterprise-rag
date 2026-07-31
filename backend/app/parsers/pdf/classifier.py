"""L1 页面分类器 — 判定每页是原生文本页、扫描页还是图文混排页

判定信号（全部来自 PyMuPDF，无外部依赖）:
    - 文字层字符数：扫描件通常 < 50
    - 图像区域覆盖率：整页大图 → 扫描页；显著但非整页 → 图文混排
"""

from __future__ import annotations

from app.core.logger import get_logger
from app.parsers.pdf.models import PageProfile, PageType

logger = get_logger(__name__)

# 判定阈值
MIN_TEXT_CHARS = 50          # 低于此字符数视为"无有效文字层"
FULL_PAGE_COVERAGE = 0.7     # 图像覆盖率高于此值 + 无文字 → 扫描页
SIGNIFICANT_COVERAGE = 0.10  # 图像覆盖率高于此值 + 有文字 → 图文混排


def _image_coverage(page) -> tuple[float, int]:
    """计算页面图像区域覆盖率（失败时保守返回 0）"""
    try:
        images = page.get_images(full=True)
    except Exception:
        return 0.0, 0
    if not images:
        return 0.0, 0

    page_area = abs(page.rect) or 1.0
    total = 0.0
    counted = 0
    for img in images:
        xref = img[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            continue
        for r in rects:
            total += abs(r)
            counted += 1
    return min(total / page_area, 1.0), counted


def classify_page(page, page_no: int) -> PageProfile:
    """对单页分类

    Args:
        page: fitz.Page 对象
        page_no: 页码（从 1 开始）

    Returns:
        PageProfile
    """
    try:
        text = page.get_text().strip()
    except Exception:
        text = ""
    coverage, image_count = _image_coverage(page)

    if len(text) < MIN_TEXT_CHARS:
        # 文字层极薄：有图 → 扫描件；无图 → 空白/近空白页，按原生处理（抽出来也是空）
        page_type = PageType.SCANNED if image_count > 0 else PageType.NATIVE
    elif coverage >= SIGNIFICANT_COVERAGE and image_count > 0:
        page_type = PageType.MIXED
    else:
        page_type = PageType.NATIVE

    profile = PageProfile(
        page_no=page_no,
        page_type=page_type,
        text_length=len(text),
        image_coverage=round(coverage, 3),
        image_count=image_count,
    )
    if page_type != PageType.NATIVE:
        logger.info(
            f"第 {page_no} 页分类为 {page_type} "
            f"(文字 {len(text)} 字符, 图像覆盖 {coverage:.0%})"
        )
    return profile


def classify_document(doc) -> list[PageProfile]:
    """对整个 PDF 逐页分类"""
    return [classify_page(page, i + 1) for i, page in enumerate(doc)]
