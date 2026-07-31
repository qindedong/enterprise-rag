"""L1 原生块级抽取 — 带 bbox 坐标提取每页的文本块/图像块

使用 ``page.get_text("blocks")`` 而非 ``page.get_text()``：
每个块携带版面坐标，供 L2 做页眉页脚过滤、多栏重组和标题识别。
扫描页在 P0 阶段仅记录告警（OCR 路径为 P2）。
"""

from __future__ import annotations

from app.core.logger import get_logger
from app.parsers.pdf.models import Block, PageContent, PageProfile, PageType

logger = get_logger(__name__)

# PyMuPDF get_text("blocks") 元组中标记图像块的类型值
_IMAGE_BLOCK_TYPE = 1


def extract_page(page, profile: PageProfile) -> PageContent:
    """块级抽取单页内容

    Args:
        page: fitz.Page 对象
        profile: L1 分类结果（决定抽取策略与告警）

    Returns:
        PageContent，块按 (y0, x0) 粗排序（多栏精确重组在 L2 做）
    """
    if profile.page_type == PageType.SCANNED:
        logger.warning(
            f"第 {profile.page_no} 页为扫描件，P0 阶段无 OCR，本页文字将为空"
        )

    content = PageContent(
        page_no=profile.page_no,
        page_type=profile.page_type,
        page_height=float(page.rect.height),
    )

    try:
        raw_blocks = page.get_text("blocks")
    except Exception as e:
        logger.error(f"第 {profile.page_no} 页块级抽取失败: {e}，回退纯文本")
        text = page.get_text().strip()
        if text:
            content.blocks.append(
                Block(kind="text", bbox=(0, 0, float(page.rect.width), content.page_height),
                      text=text, page_no=profile.page_no)
            )
        return content

    for b in raw_blocks:
        x0, y0, x1, y1, payload, _block_no, block_type = b[:7]
        if block_type == _IMAGE_BLOCK_TYPE:
            content.blocks.append(
                Block(kind="image", bbox=(x0, y0, x1, y1), page_no=profile.page_no)
            )
            continue
        text = payload.strip() if isinstance(payload, str) else ""
        if text:
            content.blocks.append(
                Block(kind="text", bbox=(x0, y0, x1, y1), text=text,
                      page_no=profile.page_no)
            )

    # get_text("blocks") 不保证返回图像块（如整页扫描图）：
    # 用 get_image_rects 补齐，保证 L2/L3 能感知图像区域
    if not any(b.kind == "image" for b in content.blocks):
        try:
            for img in page.get_images(full=True):
                for rect in page.get_image_rects(img[0]):
                    content.blocks.append(
                        Block(kind="image", bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                              page_no=profile.page_no)
                    )
        except Exception:
            pass

    # 去重：同一 xref 被多次引用时 get_image_rects 会产生重复图像块，
    # 重复块会导致重复 figure 节点和重复视觉理解 API 调用
    seen_img: set[tuple] = set()
    deduped: list[Block] = []
    for blk in content.blocks:
        if blk.kind == "image":
            key = tuple(round(v, 1) for v in blk.bbox)
            if key in seen_img:
                continue
            seen_img.add(key)
        deduped.append(blk)
    content.blocks = deduped

    content.blocks.sort(key=lambda blk: (round(blk.y0, 1), round(blk.x0, 1)))
    return content


def extract_document(doc, profiles: list[PageProfile]) -> list[PageContent]:
    """对整个 PDF 逐页抽取：原生/混排页走块级抽取，扫描页走 OCR"""
    from app.parsers.pdf.ocr_extractor import ocr_page

    pages: list[PageContent] = []
    for i, page in enumerate(doc):
        profile = profiles[i]
        if profile.page_type == PageType.SCANNED:
            pages.append(ocr_page(page, profile))
        else:
            pages.append(extract_page(page, profile))
    return pages
