"""
检索结果融合

RRF（Reciprocal Rank Fusion）融合多路检索结果：
    score(d) = Σ 1 / (k + rank_i(d))

相比分数加权融合，RRF 不要求各路分数同分布，
对向量分数（0-1 余弦）与 BM25 分数（无界）天然适配。
"""

from app.core.logger import get_logger

logger = get_logger(__name__)

RRF_K = 60  # 业界常用默认值，cormack 2009 推荐


def rrf_merge(
    *ranked_lists: list[dict],
    k: int = RRF_K,
    key: str = "chunk_id",
) -> list[dict]:
    """
    RRF 融合多路检索结果

    Args:
        ranked_lists: 各路检索结果（按相关度降序）
        k: RRF 常数（默认 60）
        key: 文档唯一标识字段

    Returns:
        融合后的候选列表（按 RRF 分数降序），score 字段为 RRF 分数，
        并附加 rrf_detail 记录各路命中名次
    """
    if not ranked_lists:
        return []

    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}
    rank_detail: dict[str, dict[int, int]] = {}

    for list_idx, ranked in enumerate(ranked_lists):
        for rank, doc in enumerate(ranked, start=1):
            doc_key = str(doc.get(key) or doc.get("id") or "")
            if not doc_key:
                continue
            scores[doc_key] = scores.get(doc_key, 0.0) + 1.0 / (k + rank)
            rank_detail.setdefault(doc_key, {})[list_idx] = rank
            # 优先保留向量路（list 0）的完整 payload；若仅 BM25 命中则保留 BM25 的
            if doc_key not in docs or list_idx == 0:
                docs[doc_key] = doc

    merged = []
    for doc_key, score in scores.items():
        doc = dict(docs[doc_key])
        doc["score"] = score
        doc["rrf_detail"] = rank_detail[doc_key]
        merged.append(doc)

    merged.sort(key=lambda x: x["score"], reverse=True)
    logger.info(f"RRF 融合: {[len(r) for r in ranked_lists]} → {len(merged)} 条 (k={k})")
    return merged
