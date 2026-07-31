"""L2 结构还原 — 把块级页面流还原为带章节/页码/条款的结构化节点流

处理步骤:
    1. 页眉页脚过滤（跨页同位置同文本的块 → 剔除）
    2. 多栏重组（按 x 坐标聚类分栏，栏内按 y 排序）
    3. 目录提取（doc.get_toc() 书签）
    4. 启发式标题/条款识别（无书签时按编号模式）
    5. 生成 StructNode 流，段落挂章节路径快照
"""

from __future__ import annotations

import re
from collections import Counter

from app.core.logger import get_logger
from app.parsers.pdf.models import (
    Block,
    DocumentStructure,
    PageContent,
    StructNode,
    TocNode,
)

logger = get_logger(__name__)

# ---- 页眉页脚判定 --------------------------------------------------------
HEADER_Y_RATIO = 0.08   # 页面上方 8% 区域
FOOTER_Y_RATIO = 0.92   # 页面下方 8% 区域
MIN_REPEAT_PAGES = 3    # 至少在 3 页重复出现才判定为页眉/页脚

# ---- 标题/条款编号模式 ----------------------------------------------------
RE_CHAPTER = re.compile(r"^第[一二三四五六七八九十百千\d]+\s*[章编部篇]")
RE_SECTION_NUM = re.compile(r"^\d+(?:\.\d+){0,3}[\s、.]\S")
RE_CN_ENUM = re.compile(r"^[一二三四五六七八九十]+、\S")
RE_APPENDIX = re.compile(r"^(附录|附件|附表)\s*[一二三四五六七八九十\d]*")
RE_CLAUSE = re.compile(r"^第\s*[一二三四五六七八九十百千\d]+\s*条")

# 中文数字 → 阿拉伯数字（仅用于条款号归一化展示，不做精确运算）
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}

MAX_HEADING_LEN = 40  # 标题行最大字符数（超过则按段落处理）


def _normalize(text: str) -> str:
    """归一化文本用于跨页比对（去空白、去页码等数字）"""
    t = re.sub(r"\s+", "", text)
    return re.sub(r"\d+", "", t)


def filter_header_footer(pages: list[PageContent]) -> int:
    """剔除跨页重复的页眉页脚块，返回剔除数量

    判定：块位于页面顶部 8% 或底部 8% 区域，且归一化文本在
    ≥ MIN_REPEAT_PAGES 个页面（或 ≥50% 页面，取更严格者）的同侧区域重复。
    """
    if len(pages) < 2:
        return 0

    threshold = max(MIN_REPEAT_PAGES, len(pages) // 2)
    # 统计每个归一化文本出现在多少页的顶部/底部区域
    top_counter: Counter[str] = Counter()
    bottom_counter: Counter[str] = Counter()
    for p in pages:
        top_seen, bottom_seen = set(), set()
        for blk in p.blocks:
            if blk.kind != "text":
                continue
            key = _normalize(blk.text)
            if not key:
                continue
            if blk.y1 <= p.page_height * HEADER_Y_RATIO:
                top_seen.add(key)
            elif blk.y0 >= p.page_height * FOOTER_Y_RATIO:
                bottom_seen.add(key)
        top_counter.update(top_seen)
        bottom_counter.update(bottom_seen)

    header_keys = {k for k, c in top_counter.items() if c >= threshold}
    footer_keys = {k for k, c in bottom_counter.items() if c >= threshold}
    if not header_keys and not footer_keys:
        return 0

    removed = 0
    for p in pages:
        kept = []
        for blk in p.blocks:
            key = _normalize(blk.text)
            is_header = key in header_keys and blk.y1 <= p.page_height * HEADER_Y_RATIO
            is_footer = key in footer_keys and blk.y0 >= p.page_height * FOOTER_Y_RATIO
            if blk.kind == "text" and (is_header or is_footer):
                removed += 1
                continue
            kept.append(blk)
        p.blocks = kept

    logger.info(
        f"页眉页脚过滤: 剔除 {removed} 个块"
        f"（页眉 {len(header_keys)} 种 / 页脚 {len(footer_keys)} 种）"
    )
    return removed


def reorder_columns(page: PageContent) -> None:
    """多栏重组：检测左右分栏并按栏重排块顺序（原地修改）

    判定：文本块明显分成左右两组（左组右缘 < 右组左缘 - 间隙），
    且两组在纵向上有重叠 → 双栏排版。先排左栏（按 y），再排右栏。
    单栏文档保持 (y, x) 阅读顺序不变。
    """
    blocks = [b for b in page.blocks if b.kind == "text"]
    if len(blocks) < 4:
        return

    xs = sorted(b.x0 for b in blocks)
    # 用最大 x0 间隙作为分栏候选点
    gaps = [(xs[i + 1] - xs[i], (xs[i] + xs[i + 1]) / 2) for i in range(len(xs) - 1)]
    max_gap, split_x = max(gaps)
    if max_gap < 40:  # 间隙不足 40pt，不视为分栏
        return

    left = [b for b in blocks if (b.x0 + b.x1) / 2 < split_x]
    right = [b for b in blocks if (b.x0 + b.x1) / 2 >= split_x]
    if len(left) < 2 or len(right) < 2:
        return

    # 两栏需在纵向上有重叠（否则只是上下排版的两个区域）
    left_y = (min(b.y0 for b in left), max(b.y1 for b in left))
    right_y = (min(b.y0 for b in right), max(b.y1 for b in right))
    overlap = min(left_y[1], right_y[1]) - max(left_y[0], right_y[0])
    if overlap <= 0:
        return

    # 左栏块右缘须整体小于右栏块左缘（否则不是干净的栏分割）
    if max(b.x1 for b in left) > min(b.x0 for b in right) + 10:
        return

    images = [b for b in page.blocks if b.kind == "image"]
    ordered = (
        sorted(left, key=lambda b: (round(b.y0, 1), round(b.x0, 1)))
        + sorted(right, key=lambda b: (round(b.y0, 1), round(b.x0, 1)))
    )
    page.blocks = ordered + images
    logger.debug(f"第 {page.page_no} 页检测为双栏排版，已按栏重组")


def extract_toc(doc) -> list[TocNode]:
    """提取 PDF 书签目录"""
    try:
        raw = doc.get_toc(simple=True)
    except Exception as e:
        logger.warning(f"目录提取失败: {e}")
        return []
    return [TocNode(level=lv, title=t.strip(), page_no=pg) for lv, t, pg in raw if t.strip()]


def _cn_to_int(text: str) -> int | None:
    """中文数字（含十/百/千）转整数，失败返回 None

    例: "三"→3, "十二"→12, "二十五"→25, "一百零三"→103
    """
    if text.isdigit():
        return int(text)
    units = {"十": 10, "百": 100, "千": 1000}
    total, current = 0, 0
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch in units:
            unit = units[ch]
            total += (current or 1) * unit
            current = 0
        elif ch == "零":
            current = 0
        else:
            return None
    total += current
    return total if total > 0 else None


def normalize_clause_no(text: str) -> str | None:
    """从文本开头提取条款号并归一化为 '第N条'，无则返回 None"""
    m = RE_CLAUSE.match(text.strip())
    if not m:
        return None
    num_text = re.sub(r"[第条\s]", "", m.group(0))
    n = _cn_to_int(num_text)
    return f"第{n}条" if n else m.group(0).replace(" ", "")


def _heading_level(text: str) -> int:
    """判定一行文本是否为标题，返回层级（0 = 非标题）"""
    t = text.strip()
    if not t or len(t) > MAX_HEADING_LEN:
        return 0
    if RE_CHAPTER.match(t) or RE_APPENDIX.match(t):
        return 1
    # 条款作标题仅限"纯标签"短行（如单独一行的"第十二条"）；
    # 带正文/句读的条款行是段落，由 normalize_clause_no 提取条款号
    if RE_CLAUSE.match(t) and len(t) <= 12 and not re.search(r"[。；;，,]", t):
        return 3
    m = re.match(r"^(\d+(?:\.\d+){0,3})[\s、.]\S", t)
    if m:
        return min(m.group(1).count(".") + 2, 5)
    if RE_CN_ENUM.match(t):
        return 2
    return 0


def _update_section_path(path: list[str], level: int, title: str) -> list[str]:
    """按标题层级更新章节路径"""
    path = path[: max(level - 1, 0)]
    path.append(title)
    return path


def build_structure(
    doc,
    pages: list[PageContent],
    file_path: str,
    page_types: dict,
) -> DocumentStructure:
    """L2 主入口：块级页面流 → 文档结构

    Args:
        doc: fitz.Document（仅用于取目录，可为 None）
        pages: L1 抽取的页面内容
        file_path: 源文件路径
        page_types: 页码 → PageType 映射
    """
    # 1. 页眉页脚过滤
    filter_header_footer(pages)
    # 2. 多栏重组
    for p in pages:
        reorder_columns(p)

    structure = DocumentStructure(
        file_path=file_path,
        page_count=len(pages),
        page_types=dict(page_types),
    )

    # 3. 目录书签（有则作为权威章节锚点）
    if doc is not None:
        structure.toc = extract_toc(doc)

    # 4+5. 标题识别 + 节点流生成
    section_path: list[str] = []
    toc_iter = iter(structure.toc)
    next_toc = next(toc_iter, None)

    for p in pages:
        for blk in p.blocks:
            if blk.kind != "text":
                # 图像块 → figure 占位节点（视觉理解为 P3，这里保留位置与页码）
                structure.nodes.append(StructNode(
                    kind="figure", text="", page_start=p.page_no, page_end=p.page_no,
                    section_path=list(section_path),
                ))
                continue

            text = blk.text.strip()
            if not text:
                continue

            # 书签锚点：到达书签页且文本与书签标题吻合时按书签层级对齐
            if next_toc and p.page_no >= next_toc.page_no:
                if _normalize(next_toc.title) in _normalize(text) or \
                        _normalize(text).startswith(_normalize(next_toc.title)[:8]):
                    section_path = _update_section_path(
                        section_path, next_toc.level, next_toc.title)
                    structure.nodes.append(StructNode(
                        kind="heading", text=next_toc.title,
                        page_start=p.page_no, page_end=p.page_no,
                        level=next_toc.level, section_path=list(section_path),
                    ))
                    next_toc = next(toc_iter, None)
                    continue

            level = _heading_level(text)
            if level > 0:
                section_path = _update_section_path(section_path, level, text)
                structure.nodes.append(StructNode(
                    kind="heading", text=text,
                    page_start=p.page_no, page_end=p.page_no,
                    level=level, section_path=list(section_path),
                ))
            else:
                structure.nodes.append(StructNode(
                    kind="paragraph", text=text,
                    page_start=p.page_no, page_end=p.page_no,
                    section_path=list(section_path),
                    clause_no=normalize_clause_no(text),
                ))

    n_headings = sum(1 for n in structure.nodes if n.kind == "heading")
    logger.info(
        f"结构还原完成: {len(structure.nodes)} 个节点 "
        f"（标题 {n_headings}，书签 {len(structure.toc)}）"
    )
    return structure
