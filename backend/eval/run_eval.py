"""
检索效果评估工具

量化检索管线质量：
- Recall@K（K=5/10）：相关文档在 Top-K 中被召回的比例
- MRR（Mean Reciprocal Rank）：第一个相关文档的排名倒数均值
- Precision@K：Top-K 中相关文档的占比

用法:
    python -m eval.run_eval          # 语义检索模式
    python -m eval.run_eval --help
"""

import argparse
import asyncio
import json
import sys
import time
from uuid import UUID

from app.infrastructure.embedding_client import EmbeddingClient
from app.infrastructure.llm_client import LLMClient
from app.infrastructure.qdrant_client import QdrantStore
from app.rag.bm25_retriever import BM25Retriever
from app.rag.pipeline import RetrievalPipeline
from app.rag.query_rewriter import QueryRewriter
from app.rag.reranker import Reranker

# 用 requests 调后端 API（不直接连 DB）
HEADERS = {"Content-Type": "application/json"}


async def load_queries(path: str) -> list[dict]:
    """加载标注查询"""
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def _normalize_title(title: str) -> str:
    """去掉时间戳前缀和扩展名（如 20260730200255_公司考勤制度.md → 公司考勤制度）"""
    import re
    # 去掉前导时间戳前缀
    title = re.sub(r"^\d{14}_", "", title)
    # 去掉扩展名
    title = re.sub(r"\.\w+$", "", title)
    return title


def recall_at_k(relevant: set, retrieved: list, k: int) -> float:
    """计算 Recall@K"""
    top_k_titles = {_normalize_title(r.get("document_title", "")) for r in retrieved[:k]}
    recalled = relevant & top_k_titles
    return len(recalled) / len(relevant) if relevant else 1.0


def mrr(relevant: set, retrieved: list) -> float:
    """计算 MRR（第一个相关文档的排名倒数）"""
    for rank, doc in enumerate(retrieved, start=1):
        if _normalize_title(doc.get("document_title", "")) in relevant:
            return 1.0 / rank
    return 0.0


def precision_at_k(relevant: set, retrieved: list, k: int) -> float:
    """计算 Precision@K"""
    top_k_titles = {_normalize_title(r.get("document_title", "")) for r in retrieved[:k]}
    relevant_in_k = relevant & top_k_titles
    return len(relevant_in_k) / k


async def run_eval(
    kb_id: str,
    mode: str = "vector",
    queries_file: str = "eval/queries.jsonl",
):
    """运行评估主流程"""
    queries = await load_queries(queries_file)
    if not queries:
        print("未找到评估查询数据")
        return

    embed_client = EmbeddingClient()
    qdrant_store = QdrantStore()
    llm_client = LLMClient()
    query_rewriter = QueryRewriter(llm_client)
    reranker = Reranker()

    from app.core.database import async_session

    bm25_retriever = BM25Retriever(async_session)
    pipeline = RetrievalPipeline(
        embed_client, qdrant_store, query_rewriter, reranker, bm25_retriever
    )

    print(f"评估模式: {mode}")
    print(f"知识库 ID: {kb_id}")
    print(f"查询数量: {len(queries)}")
    print("=" * 60)

    all_recall_5 = []
    all_recall_10 = []
    all_mrr = []
    all_prec_5 = []
    all_latency_ms = []
    failed = 0

    for i, q in enumerate(queries):
        question = q["question"]
        relevant_titles = set(q.get("relevant_docs", []))
        if not relevant_titles:
            print(f"  [{i + 1}] 跳过（无标注）: {question[:50]}...")
            continue

        try:
            start = time.time()
            docs = await pipeline.retrieve(
                question,
                UUID(kb_id),
                retrieval_top_k=50,
                rerank_top_k=10,
                mode=mode,
            )
            elapsed = (time.time() - start) * 1000
            all_latency_ms.append(elapsed)

            r5 = recall_at_k(relevant_titles, docs, 5)
            r10 = recall_at_k(relevant_titles, docs, 10)
            _mrr = mrr(relevant_titles, docs)
            p5 = precision_at_k(relevant_titles, docs, 5)

            all_recall_5.append(r5)
            all_recall_10.append(r10)
            all_mrr.append(_mrr)
            all_prec_5.append(p5)

            # 显示每个查询的简要结果
            retrieved_titles = [d.get("document_title", "") for d in docs[:5]]
            status = "✓" if r5 > 0 else "✗"
            print(f"  [{i + 1}] {status} '{question[:40]}...' → Recall@5={r5:.2f}")
            print(f"       相关: {relevant_titles}")
            print(f"       命中: {[t for t in retrieved_titles if t in relevant_titles]}")
        except Exception as e:
            failed += 1
            print(f"  [{i + 1}] ✗ 失败: '{question[:40]}...' → {e}")

    # 汇总
    n = len(all_recall_5)
    print()
    print("=" * 60)
    print(f"评估完成（{n} 条有效查询, {failed} 条失败）")
    print(f"  Recall@5:  平均 {sum(all_recall_5) / n:.3f} ({sum(1 for r in all_recall_5 if r > 0)}/{n} 命中)")
    print(f"  Recall@10: 平均 {sum(all_recall_10) / n:.3f}")
    print(f"  MRR:       平均 {sum(all_mrr) / n:.3f}")
    print(f"  Precision@5: 平均 {sum(all_prec_5) / n:.3f}")
    print(f"  检索延迟:   平均 {sum(all_latency_ms) / n:.0f}ms (P50), {sorted(all_latency_ms)[n // 2]:.0f}ms (P50)")

    # 按难度分组
    difficulties = {}
    for q, r5 in zip(queries, all_recall_5):
        d = q.get("difficulty", "unknown")
        difficulties.setdefault(d, []).append(r5)
    print("  按难度:")
    for d, scores in sorted(difficulties.items()):
        print(f"    {d}: Recall@5 平均 {sum(scores) / len(scores):.3f} ({len(scores)} 条)")

    # 保存详细结果
    result = {
        "mode": mode,
        "kb_id": kb_id,
        "query_count": n,
        "failed_count": failed,
        "recall_5": sum(all_recall_5) / n,
        "recall_10": sum(all_recall_10) / n,
        "mrr": sum(all_mrr) / n,
        "precision_5": sum(all_prec_5) / n,
        "avg_latency_ms": sum(all_latency_ms) / n,
    }
    out_path = f"eval/results/{mode}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  结果已保存: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="检索效果评估")
    parser.add_argument("--kb-id", default="eb765c6b-c7c6-452f-9617-8e6f6e07f8dc", help="知识库 ID")
    parser.add_argument(
        "--mode", default="vector", choices=["vector", "bm25", "hybrid"], help="检索模式"
    )
    parser.add_argument("--queries", default="eval/queries.jsonl", help="查询文件路径")
    args = parser.parse_args()

    asyncio.run(run_eval(args.kb_id, args.mode, args.queries))


if __name__ == "__main__":
    main()
