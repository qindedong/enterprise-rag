"""L1 OCR 抽取路径 — 扫描页渲染为图像，经 RapidOCR 识别为带坐标的文本块

关键设计：OCR 输出与原生块级抽取**完全同构**（Block + bbox），
L2 的页眉页脚过滤、多栏重组、标题识别和 L3 的切片对扫描件零感知。

引擎：RapidOCR（ONNX runtime，模型随包内置无需下载，CPU 约 1-2 秒/页）。
"""

from __future__ import annotations

from app.core.logger import get_logger
from app.parsers.pdf.models import Block, PageContent, PageProfile, PageType

logger = get_logger(__name__)

# 渲染分辨率：300 DPI 是 OCR 精度与速度的平衡点
RENDER_DPI = 300
# 单页识别平均置信度低于此值时打标提示
LOW_CONFIDENCE_THRESHOLD = 0.7

_ocr_engine = None


def _get_engine():
    """延迟初始化 OCR 引擎（模型随 wheel 内置，首次加载约 1-2s）"""
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
        logger.info("RapidOCR 引擎初始化完成（模型包内置，无需下载）")
    return _ocr_engine


def ocr_available() -> bool:
    """检查 OCR 依赖是否可用（不可用时扫描页降级为空 + 告警，不崩溃）"""
    try:
        _get_engine()
        return True
    except Exception as e:
        logger.warning(f"OCR 引擎不可用: {e}")
        return False


def ocr_page(page, profile: PageProfile) -> PageContent:
    """对扫描页执行 OCR，返回与原生抽取同构的 PageContent

    Args:
        page: fitz.Page 对象
        profile: L1 页面分类结果（应为 SCANNED）

    Returns:
        PageContent：文本块带 bbox，ocr_confidence 为全页平均置信度
    """
    content = PageContent(
        page_no=profile.page_no,
        page_type=profile.page_type,
        page_height=float(page.rect.height),
    )

    try:
        engine = _get_engine()
    except Exception as e:
        logger.warning(f"第 {profile.page_no} 页 OCR 引擎不可用: {e}，本页为空")
        return content

    try:
        import fitz

        zoom = RENDER_DPI / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img_bytes = pix.tobytes("png")
    except Exception as e:
        logger.error(f"第 {profile.page_no} 页渲染失败: {e}")
        return content

    try:
        result, _elapse = engine(img_bytes)
    except Exception as e:
        logger.error(f"第 {profile.page_no} 页 OCR 识别失败: {e}")
        return content

    if not result:
        logger.warning(f"第 {profile.page_no} 页 OCR 未识别到文字")
        _preserve_image_blocks(page, content)
        return content

    # 坐标换算：OCR 在渲染图上识别，需除 zoom 还原为 PDF 坐标
    confidences: list[float] = []
    for box, text, confidence in result:
        text = (text or "").strip()
        if not text:
            continue
        xs = [p[0] / zoom for p in box]
        ys = [p[1] / zoom for p in box]
        content.blocks.append(Block(
            kind="text",
            bbox=(min(xs), min(ys), max(xs), max(ys)),
            text=text,
            page_no=profile.page_no,
        ))
        confidences.append(float(confidence))

    if confidences:
        content.ocr_confidence = round(sum(confidences) / len(confidences), 3)
        if content.ocr_confidence < LOW_CONFIDENCE_THRESHOLD:
            logger.warning(
                f"第 {profile.page_no} 页 OCR 置信度偏低 "
                f"({content.ocr_confidence:.0%})，建议人工校对"
            )

    content.blocks.sort(key=lambda b: (round(b.y0, 1), round(b.x0, 1)))
    logger.info(
        f"第 {profile.page_no} 页 OCR 完成: {len(content.blocks)} 个文本块, "
        f"平均置信度 {content.ocr_confidence or 0:.0%}"
    )
    return content


def _preserve_image_blocks(page, content: PageContent) -> None:
    """OCR 无文字时保留图像块，让 L2 仍能生成图表占位节点（P3 视觉理解用）"""
    try:
        for img in page.get_images(full=True):
            for rect in page.get_image_rects(img[0]):
                content.blocks.append(Block(
                    kind="image",
                    bbox=(rect.x0, rect.y0, rect.x1, rect.y1),
                    page_no=content.page_no,
                ))
    except Exception:
        pass
