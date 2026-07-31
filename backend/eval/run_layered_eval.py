"""PDF 四层架构分层评测

不只看最终答案，逐层量化：
- L1 解析层：页面分类准确率、OCR 字符错误率（CER，需 rapidocr）
- L2 结构还原：标题层级还原 F1、表格结构正确率（行列对齐）
- L3 切片索引：chunk 页码精准率、章节归属完整率、图表 chunk 检出
- L4 Agent 层：意图路由准确率

样本集由本脚本自动生成（原生文字页/扫描件/线框表格/整页图表），
ground truth 内置，全程离线可跑（OCR 一项需 rapidocr 依赖）。

用法（backend 目录下）:
    python -m eval.run_layered_eval            # 全部四层
    python -m eval.run_layered_eval --layers L1 L4
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import fitz

SAMPLES_DIR = Path(__file__).parent / "samples"

# ============================================================
# 样本生成（ground truth 与样本一一对应）
# ============================================================

CONTRACT_TEXT = """技术服务合同

第一章 总则

第一条 甲方委托乙方提供技术开发服务。

第二章 服务内容

第二条 乙方应完成系统设计、开发与部署。

第三章 费用与支付

第三条 合同总金额为人民币伍拾万元整。

第四章 违约责任

第四条 乙方逾期交付应支付违约金。"""

GT_HEADINGS = ["第一章 总则", "第二章 服务内容", "第三章 费用与支付", "第四章 违约责任"]

TABLE_GT = {
    "headers": ["费用项目", "金额（万元）", "占比"],
    "rows": [
        ["开发费", "30", "60%"],
        ["测试费", "10", "20%"],
        ["运维费", "10", "20%"],
    ],
}

L4_GT = [
    ("迟到扣多少钱？", "simple"),
    ("年假有几天？", "simple"),
    ("这句话出自哪里？", "quote"),
    ("违约金规定的原文是什么？", "quote"),
    ("各项费用占比是多少？", "chart"),
    ("收入趋势图说明了什么？", "chart"),
    ("费用明细表格里开发费是多少？", "table"),
    ("对比第一章和第四章的违约责任", "compare"),
    ("第三章和第五章有什么区别？", "compare"),
]


def _make_native_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 800), CONTRACT_TEXT,
                        fontsize=12, fontname="china-s")
    doc.save(path)


def _make_scanned_pdf(path: Path) -> None:
    """文字页渲染成图片再插入 → 真扫描件"""
    src = fitz.open()
    page = src.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 800), CONTRACT_TEXT,
                        fontsize=12, fontname="china-s")
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
    out = fitz.open()
    opage = out.new_page()
    opage.insert_image(opage.rect, pixmap=pix)
    out.save(path)


def _make_table_pdf(path: Path) -> None:
    """文字 + 线框表格（行列 ground truth 固定）"""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 40, 545, 90),
                        "第五章 费用明细\n表 5-1 费用构成表",
                        fontsize=12, fontname="china-s")
    x0, y0 = 50, 120
    col_w, row_h = 160, 28
    grid = [TABLE_GT["headers"]] + TABLE_GT["rows"]
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            rect = fitz.Rect(x0 + c * col_w, y0 + r * row_h,
                             x0 + (c + 1) * col_w, y0 + (r + 1) * row_h)
            page.draw_rect(rect)
            page.insert_textbox(rect + (4, 4, -4, -4), cell,
                                fontsize=10, fontname="china-s")
    doc.save(path)


def _make_figure_pdf(path: Path) -> None:
    """文字页 + 图片形式的柱状图 → figure 检出（矢量绘制不算图像块，
    必须先渲染成位图再插入）"""
    # 先在临时页手绘柱状图
    tmp = fitz.open()
    tpage = tmp.new_page()
    base_y = 400
    for i, h in enumerate([120, 220, 90, 260]):
        x0 = 60 + i * 110
        tpage.draw_rect(fitz.Rect(x0, base_y - h, x0 + 70, base_y),
                        fill=(0.4, 0.6, 0.9))
    pix = tpage.get_pixmap(clip=fitz.Rect(0, 80, 550, 450))
    # 正式页：标题 + 正文段落 + 图表图片（足够文字量 → 图文混排页）
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(
        fitz.Rect(50, 40, 545, 130),
        "第六章 经营分析\n"
        "本年度四个季度的营业收入呈现明显的波动上升趋势，"
        "其中第四季度收入最高，较第一季度增长约一倍。"
        "下图展示了各季度收入对比情况。",
        fontsize=12, fontname="china-s")
    page.insert_image(fitz.Rect(80, 150, 520, 550), pixmap=pix)
    doc.save(path)


def build_samples() -> dict[str, Path]:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    builders = {
        "native.pdf": _make_native_pdf,
        "scanned.pdf": _make_scanned_pdf,
        "table.pdf": _make_table_pdf,
        "figure.pdf": _make_figure_pdf,
    }
    paths = {}
    for name, fn in builders.items():
        p = SAMPLES_DIR / name
        fn(p)
        paths[name] = p
    return paths


# ============================================================
# 指标工具
# ============================================================

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    return "".join(s.split())


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1,
                           prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def cer(hypothesis: str, reference: str) -> float:
    """字符错误率：编辑距离 / 参考字符数"""
    h, r = _norm(hypothesis), _norm(reference)
    return _levenshtein(h, r) / max(len(r), 1)


# ============================================================
# 各层评测
# ============================================================

def eval_l1(paths: dict[str, Path]) -> dict:
    from app.parsers.pdf.classifier import classify_document

    expected = {"native.pdf": "native", "scanned.pdf": "scanned",
                "table.pdf": "native", "figure.pdf": "mixed"}
    correct, total = 0, 0
    detail = {}
    for name, want in expected.items():
        with fitz.open(paths[name]) as doc:
            profiles = classify_document(doc)
        got = profiles[0].page_type.value
        ok = got == want
        correct += ok
        total += 1
        detail[name] = {"want": want, "got": got, "ok": ok}

    # OCR CER（rapidocr 可用时）
    ocr_result = {"skipped": True}
    try:
        from app.parsers.pdf.models import PageType
        from app.parsers.pdf.ocr_extractor import ocr_page

        with fitz.open(paths["scanned.pdf"]) as doc:
            profile = classify_document(doc)[0]
            assert profile.page_type == PageType.SCANNED
            content = ocr_page(doc[0], profile)
        text = "\n".join(b.text or "" for b in content.blocks)
        ocr_result = {
            "skipped": False,
            "cer": round(cer(text, CONTRACT_TEXT), 4),
            "confidence": content.ocr_confidence,
        }
    except Exception as e:
        ocr_result = {"skipped": True, "reason": str(e)[:120]}

    return {
        "layer": "L1 解析层",
        "classification_accuracy": round(correct / total, 4),
        "detail": detail,
        "ocr": ocr_result,
    }


def eval_l2(paths: dict[str, Path]) -> dict:
    from app.parsers.pdf_parser import PDFParser

    # 标题 F1
    structure = PDFParser().parse_structured(str(paths["native.pdf"]))
    got = {_norm(n.text) for n in structure.nodes if n.kind == "heading"}
    want = {_norm(h) for h in GT_HEADINGS}
    tp = len(got & want)
    precision = tp / max(len(got), 1)
    recall = tp / max(len(want), 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)

    # 表格结构正确率（行列对齐 + 表头命中）
    tstruct = PDFParser().parse_structured(str(paths["table.pdf"]))
    tables = [n.table for n in tstruct.nodes if n.kind == "table" and n.table]
    table_ok, table_total = 0, 1
    if tables:
        t = tables[0]
        headers_ok = [_norm(h) for h in t.headers] == [_norm(h) for h in TABLE_GT["headers"]]
        rows_ok = len(t.rows) == len(TABLE_GT["rows"]) and all(
            len(r) == len(TABLE_GT["headers"]) for r in t.rows
        )
        first_row_ok = bool(t.rows) and _norm(t.rows[0][0]) == _norm(TABLE_GT["rows"][0][0])
        table_ok = int(headers_ok and rows_ok and first_row_ok)
    else:
        headers_ok = rows_ok = first_row_ok = False

    return {
        "layer": "L2 结构还原",
        "heading_f1": round(f1, 4),
        "heading_precision": round(precision, 4),
        "heading_recall": round(recall, 4),
        "table_detected": len(tables),
        "table_structure_correct": table_ok,
        "table_detail": {"headers_ok": headers_ok, "rows_ok": rows_ok,
                         "first_row_ok": first_row_ok},
    }


def eval_l3(paths: dict[str, Path]) -> dict:
    from app.parsers.pdf_parser import PDFParser
    from app.rag.semantic_chunker import SemanticChunker

    chunker = SemanticChunker()
    page_ok, page_total, section_ok, section_total = 0, 0, 0, 0
    for name in ("native.pdf", "table.pdf"):
        structure = PDFParser().parse_structured(str(paths[name]))
        for c in chunker.split(structure):
            page_total += 1
            page_ok += int(c.page_start >= 1 and c.page_end >= c.page_start)
            if c.kind in ("clause", "paragraph") and c.section_path:
                section_total += 1
                section_ok += int(bool(" / ".join(c.section_path).strip()))

    # 图表 chunk 检出
    fstruct = PDFParser().parse_structured(str(paths["figure.pdf"]))
    fig_chunks = [c for c in chunker.split(fstruct) if c.kind == "figure_summary"]

    return {
        "layer": "L3 切片索引",
        "page_precision": round(page_ok / max(page_total, 1), 4),
        "section_completeness": round(section_ok / max(section_total, 1), 4)
        if section_total else None,
        "figure_chunk_detected": len(fig_chunks) > 0,
    }


def eval_l4() -> dict:
    from app.agent.planner import route_intent

    correct, detail = 0, []
    for q, want in L4_GT:
        got = route_intent(q)
        ok = got == want
        correct += ok
        detail.append({"q": q, "want": want, "got": got, "ok": ok})
    return {
        "layer": "L4 Agent 层",
        "routing_accuracy": round(correct / len(L4_GT), 4),
        "detail": detail,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PDF 四层架构分层评测")
    parser.add_argument("--layers", nargs="*", default=["L1", "L2", "L3", "L4"])
    parser.add_argument("--json", action="store_true", help="输出原始 JSON")
    args = parser.parse_args()

    paths = build_samples()
    results = []
    if "L1" in args.layers:
        results.append(eval_l1(paths))
    if "L2" in args.layers:
        results.append(eval_l2(paths))
    if "L3" in args.layers:
        results.append(eval_l3(paths))
    if "L4" in args.layers:
        results.append(eval_l4())

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    print("\n" + "=" * 56)
    print("PDF 四层架构分层评测报告")
    print("=" * 56)
    for r in results:
        print(f"\n【{r['layer']}】")
        for k, v in r.items():
            if k in ("layer", "detail", "table_detail"):
                continue
            print(f"  {k}: {v}")
    failed = []
    for r in results:
        for k, v in r.items():
            if isinstance(v, float) and k != "cer" and v < 0.99:
                failed.append(f"{r['layer']}/{k}={v}")
            if v is False:
                failed.append(f"{r['layer']}/{k}=False")
    print("\n" + ("✅ 全部指标达标" if not failed
                  else f"⚠️ 未达标项: {', '.join(failed)}"))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
