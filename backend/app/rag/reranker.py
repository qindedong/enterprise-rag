"""
重排序器

使用 Cross-Encoder 模型对检索结果进行精排。
Top-50 → Top-10.
"""

from app.core.logger import get_logger

logger = get_logger(__name__)


class Reranker:
    """重排序器 — Cross-Encoder 模型

    v1.0 使用简单排序（基于 Qdrant score），v1.5 升级为 bge-reranker-v2-m3.
    """

    def __init__(self):
        self._model = None  # 延迟加载
        logger.info("Reranker 初始化完成（v1.0 使用 Qdrant score 排序）")

    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 10,
    ) -> list[dict]:
        """
        重排序检索结果

        Args:
            query: 用户查询
            candidates: Qdrant 返回的候选文档列表（含 score 和 payload）
            top_k: 返回数量（默认 10）

        Returns:
            重排序后的 Top-K 文档
        """
        if not candidates:
            return []

        # v1.0 简单排序策略：按 Qdrant score 降序 + 相似度过滤
        sorted_candidates = sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)

        # 多样性过滤（相似度 > 0.95 视为重复）
        filtered = self._diversity_filter(sorted_candidates, threshold=0.95)

        result = filtered[:top_k]
        logger.info(f"重排序完成: {len(candidates)} → {len(result)} 条")
        return result

    def _diversity_filter(self, candidates: list[dict], threshold: float = 0.95) -> list[dict]:
        """基于相似度的多样性过滤"""
        if len(candidates) <= 1:
            return candidates

        filtered = [candidates[0]]
        for cand in candidates[1:]:
            is_dup = False
            for kept in filtered:
                # 基于 chunk 内容前 200 字符去重
                if cand.get("content", "")[:200] == kept.get("content", "")[:200]:
                    is_dup = True
                    break
            if not is_dup:
                filtered.append(cand)

        if len(filtered) < len(candidates):
            logger.info(f"多样性过滤: {len(candidates)} → {len(filtered)} 条")
        return filtered
