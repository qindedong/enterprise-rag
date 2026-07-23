"""
检索效果评估脚本

对 POST /api/v1/knowledge-bases/{kb_id}/search 接口运行标注数据集，
计算 Recall@K 与 MRR@10，用于对比不同检索模式（vector / bm25 / hybrid）。

用法:
    python backend/scripts/evaluate_retrieval.py \
        --base-url http://localhost:8000 \
        --kb-id <知识库UUID> \
        --dataset backend/eval/queries.jsonl \
        --mode vector \
        --output backend/eval/results/vector_baseline.json

前置条件:
    1. 后端服务已启动（uvicorn app.main:app）
    2. 知识库中已上传 test-data 下的三份文档，且文档标题与
       数据集中的 relevant_docs 匹配（按文件名去后缀匹配）
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx


def load_dataset(path: Path) -> list[dict]:
    """加载 JSONL 标注数据集"""
    items = []
    with path.open(encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if "question" not in item or "relevant_docs" not in item:
                raise ValueError(f"数据集第 {lineno} 行缺少 question 或 relevant_docs 字段")
            items.append(item)
    return items


def doc_matches(result_title: str, relevant_docs: list[str]) -> bool:
    """判断检索结果的文档标题是否命中标注（按包含关系，兼容文件名后缀）"""
    title = result_title.lower()
    return any(doc.lower() in title for doc in relevant_docs)


async def run_query(
    client: httpx.AsyncClient,
    base_url: str,
    kb_id: str,
    item: dict,
    mode: str,
    top_k: int,
    candidate_k: int,
) -> dict:
    """执行单条查询并计算命中情况"""
    resp = await client.post(
        f"{base_url}/api/v1/knowledge-bases/{kb_id}/search",
        json={
            "question": item["question"],
            "mode": mode,
            "top_k": top_k,
            "candidate_k": candidate_k,
        },
    )
    resp.raise_for_status()
    payload = resp.json()["data"]

    results = payload["results"]
    relevant = item["relevant_docs"]

    # 首个命中的名次（1-based），未命中为 None
    first_hit_rank = None
    for r in results:
        if doc_matches(r["document_title"], relevant):
            first_hit_rank = r["rank"]
            break

    hits_at_k = {k: first_hit_rank is not None and first_hit_rank <= k for k in (1, 3, 5, 10)}
    reciprocal_rank = 1.0 / first_hit_rank if first_hit_rank else 0.0

    return {
        "question": item["question"],
        "difficulty": item.get("difficulty", ""),
        "relevant_docs": relevant,
        "first_hit_rank": first_hit_rank,
        "hits_at_k": hits_at_k,
        "reciprocal_rank": reciprocal_rank,
        "top_results": [
            {"rank": r["rank"], "document_title": r["document_title"], "score": r["score"]}
            for r in results[:5]
        ],
        "latency_ms": payload.get("processing_time_ms", 0),
    }


def aggregate(details: list[dict]) -> dict:
    """汇总指标"""
    n = len(details)
    if n == 0:
        return {}

    metrics = {
        "total_queries": n,
        "recall@1": sum(d["hits_at_k"][1] for d in details) / n,
        "recall@3": sum(d["hits_at_k"][3] for d in details) / n,
        "recall@5": sum(d["hits_at_k"][5] for d in details) / n,
        "recall@10": sum(d["hits_at_k"][10] for d in details) / n,
        "mrr@10": sum(d["reciprocal_rank"] for d in details) / n,
        "avg_latency_ms": sum(d["latency_ms"] for d in details) / n,
    }

    # 按难度分层
    by_difficulty: dict[str, list[dict]] = {}
    for d in details:
        by_difficulty.setdefault(d["difficulty"] or "unknown", []).append(d)
    metrics["by_difficulty"] = {
        diff: {
            "count": len(items),
            "recall@5": sum(d["hits_at_k"][5] for d in items) / len(items),
            "mrr@10": sum(d["reciprocal_rank"] for d in items) / len(items),
        }
        for diff, items in sorted(by_difficulty.items())
    }
    return metrics


def print_report(metrics: dict, details: list[dict], mode: str) -> None:
    """打印人类可读报告"""
    print(f"\n{'=' * 60}")
    print(f"检索评估报告 — mode: {mode}, 查询数: {metrics['total_queries']}")
    print(f"{'=' * 60}")
    print(f"  Recall@1 : {metrics['recall@1']:.3f}")
    print(f"  Recall@3 : {metrics['recall@3']:.3f}")
    print(f"  Recall@5 : {metrics['recall@5']:.3f}")
    print(f"  Recall@10: {metrics['recall@10']:.3f}")
    print(f"  MRR@10   : {metrics['mrr@10']:.3f}")
    print(f"  平均延迟 : {metrics['avg_latency_ms']:.0f} ms")

    print("\n按难度分层:")
    for diff, m in metrics["by_difficulty"].items():
        print(f"  [{diff}] n={m['count']}, Recall@5={m['recall@5']:.3f}, MRR@10={m['mrr@10']:.3f}")

    misses = [d for d in details if d["first_hit_rank"] is None]
    if misses:
        print(f"\n未命中查询 ({len(misses)} 条):")
        for d in misses:
            print(f"  ✗ {d['question']}")
            print(
                f"    期望: {d['relevant_docs']}, 实际 Top-3: "
                f"{[r['document_title'] for r in d['top_results'][:3]]}"
            )


async def main() -> int:
    parser = argparse.ArgumentParser(description="检索效果评估（Recall@K / MRR）")
    parser.add_argument("--base-url", default="http://localhost:8000", help="后端服务地址")
    parser.add_argument("--kb-id", required=True, help="知识库 UUID")
    parser.add_argument("--dataset", default="backend/eval/queries.jsonl", help="标注数据集路径")
    parser.add_argument("--mode", default="vector", choices=["vector", "bm25", "hybrid"])
    parser.add_argument("--top-k", type=int, default=10, help="重排后返回数")
    parser.add_argument("--candidate-k", type=int, default=50, help="向量检索候选数")
    parser.add_argument("--output", default=None, help="结果 JSON 输出路径")
    parser.add_argument("--timeout", type=float, default=60.0, help="单查询超时（秒）")
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        print(f"错误: 数据集不存在: {dataset_path}", file=sys.stderr)
        return 1

    dataset = load_dataset(dataset_path)
    print(f"加载数据集: {len(dataset)} 条查询, mode={args.mode}, kb={args.kb_id}")

    start = time.time()
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        # 逐条执行（评估不在乎速度，避免压垮服务；LLM 查询改写是串行瓶颈）
        details = []
        for i, item in enumerate(dataset, 1):
            try:
                detail = await run_query(
                    client,
                    args.base_url,
                    args.kb_id,
                    item,
                    args.mode,
                    args.top_k,
                    args.candidate_k,
                )
                details.append(detail)
                status = f"rank={detail['first_hit_rank']}" if detail["first_hit_rank"] else "MISS"
                print(f"  [{i}/{len(dataset)}] {status:>8}  {item['question'][:40]}")
            except httpx.HTTPError as e:
                print(
                    f"  [{i}/{len(dataset)}] ERROR  {item['question'][:40]}: {e}", file=sys.stderr
                )
                details.append(
                    {
                        "question": item["question"],
                        "difficulty": item.get("difficulty", ""),
                        "relevant_docs": item["relevant_docs"],
                        "first_hit_rank": None,
                        "hits_at_k": dict.fromkeys((1, 3, 5, 10), False),
                        "reciprocal_rank": 0.0,
                        "top_results": [],
                        "latency_ms": 0,
                        "error": str(e),
                    }
                )

    metrics = aggregate(details)
    metrics["mode"] = args.mode
    metrics["kb_id"] = args.kb_id
    metrics["top_k"] = args.top_k
    metrics["candidate_k"] = args.candidate_k
    metrics["wall_time_s"] = time.time() - start

    print_report(metrics, details, args.mode)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps({"metrics": metrics, "details": details}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n结果已保存: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
