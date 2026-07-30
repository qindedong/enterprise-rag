"""
RAG 回答质量检查（幻觉检测 + 引用完整性校验）

集成于 RAGService._generate()，在 LLM 回答后执行：
1. 引用越界检测：引用的 [N] 是否在 1-max 范围内
2. 断言无引用检测：回答中有事实陈述但无引用支撑
3. 内容匹配度：引用的内容是否与检索内容一致

用法：
    from app.rag.quality_checker import check_answer
    warnings = await check_answer(answer, citations)
"""
import re

from app.core.logger import get_logger

logger = get_logger(__name__)


def check_answer(answer: str, citations: list[dict]) -> list[dict]:
    """
    检查 RAG 回答质量，返回警告列表

    Args:
        answer: LLM 生成的回答
        citations: 有效引用列表（已验证的 citations）

    Returns:
        警告列表 [{"severity": "warning"|"info", "message": "..."}]
    """
    warnings: list[dict] = []

    # 1. 引用越界检测
    cited_nums = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
    max_index = len(citations)
    hallucinated = [n for n in cited_nums if n < 1 or n > max_index]
    if hallucinated:
        warnings.append(
            {
                "severity": "warning",
                "message": (
                    f"疑似幻觉引用: 索引 {hallucinated} 超出有效范围 1-{max_index}。"
                    "该引用可能来自历史对话或 LLM 编造。"
                ),
            }
        )

    # 2. 断言无引用检测
    # 去除 Markdown 标记和空白后检查
    plain_text = re.sub(r"[*#`\-\>\|]", "", answer).strip()

    # 直接按句号分割检查
    sentences = re.split(r"[。！？\n]", plain_text)
    factual_sentences = [
        s.strip()
        for s in sentences
        if len(s.strip()) > 8 and "无法回答" not in s
    ]

    cited_indices_in_text = [int(n) for n in re.findall(r"\[(\d+)\]", answer)]

    if len(factual_sentences) >= 2 and not cited_indices_in_text:
        warnings.append(
            {
                "severity": "warning",
                "message": (
                    f"疑似幻觉: 回答含 {len(factual_sentences)} 条断言但无引用标记。"
                    "建议检查 LLM 是否基于实际检索内容生成了回答。"
                ),
            }
        )

    # 3. 内容匹配度（快速检查引用内容是否出现在回答中）
    for citation in citations[: min(len(citations), 8)]:
        snippet = citation.get("content_snippet", "")
        if snippet and len(snippet) > 20:
            # 取 snippet 的前 30 个字符做模糊匹配
            key = snippet[:30]
            if key not in answer:
                warnings.append(
                    {
                        "severity": "info",
                        "message": (
                            f"引用 [{citation.get('index', '?')}] "
                            "的内容片段在回答中未找到精确匹配。"
                        ),
                    }
                )

    if warnings:
        warn_msgs = "; ".join(
            f"[{w['severity']}] {w['message'][:100]}" for w in warnings
        )
        logger.warning(f"回答质量警告 ({len(warnings)} 条): {warn_msgs}")

    return warnings
