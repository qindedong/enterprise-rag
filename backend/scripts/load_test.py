"""
性能压测脚本

对检索/问答接口做并发压测，输出延迟分位数与吞吐。
验收标准（TEST_PLAN）：100 并发下 P95 < 15s。

用法:
    # 检索接口（轻量，直接上 100 并发）
    python backend/scripts/load_test.py \
        --kb-id <UUID> --endpoint search --mode hybrid \
        --concurrency 100 --requests 300

    # 问答接口（重量级，含 LLM 调用，建议先小并发试）
    python backend/scripts/load_test.py \
        --kb-id <UUID> --endpoint chat \
        --concurrency 20 --requests 40
"""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

# 压测用问题池（覆盖三篇文档主题，避免单查询缓存效应）
QUESTIONS = [
    "年假有几天？上限是多少？",
    "9:40 到公司算迟到吗？怎么处理？",
    "周末加班的补偿标准是什么？",
    "公积金缴存比例是多少？",
    "重疾险保额多少？覆盖多少种疾病？",
    "住房补贴标准是怎样的？",
    "一个 Sprint 多长时间？站会几点？",
    "代码合入前要经过什么流程？",
    "灰度发布是怎么逐步放量的？",
    "P0 故障全年允许几次？",
    "高温补贴发几个月？",
    "请假审批流程是怎样的？",
]


def percentile(sorted_data: list[float], p: float) -> float:
    """线性插值分位数"""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_data) - 1)
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


async def worker(
    name: int,
    client: httpx.AsyncClient,
    url: str,
    payload_fn,
    queue: asyncio.Queue,
    results: list,
) -> None:
    """从队列取任务执行，记录 (latency_ms, ok, error)"""
    while True:
        try:
            idx = queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        payload = payload_fn(idx)
        start = time.perf_counter()
        try:
            resp = await client.post(url, json=payload)
            latency = (time.perf_counter() - start) * 1000
            ok = resp.status_code == 200
            results.append((latency, ok, None if ok else f"HTTP {resp.status_code}"))
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            results.append((latency, False, f"{type(e).__name__}: {e}"))
        queue.task_done()


async def main() -> int:
    parser = argparse.ArgumentParser(description="检索/问答接口压测")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--kb-id", required=True)
    parser.add_argument("--endpoint", choices=["search", "chat"], default="search")
    parser.add_argument("--mode", choices=["vector", "bm25", "hybrid"], default="hybrid")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--requests", type=int, default=300, help="总请求数")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    if args.endpoint == "search":
        url = f"{args.base_url}/api/v1/knowledge-bases/{args.kb_id}/search"
        payload_fn = lambda i: {  # noqa: E731
            "question": QUESTIONS[i % len(QUESTIONS)],
            "mode": args.mode,
            "top_k": 10,
        }
    else:
        url = f"{args.base_url}/api/v1/knowledge-bases/{args.kb_id}/chat/sync"
        payload_fn = lambda i: {"question": QUESTIONS[i % len(QUESTIONS)]}  # noqa: E731

    queue: asyncio.Queue = asyncio.Queue()
    for i in range(args.requests):
        queue.put_nowait(i)

    results: list = []
    print(f"压测开始: {args.endpoint} (mode={args.mode if args.endpoint == 'search' else '-'})")
    print(f"  并发 {args.concurrency}, 总请求 {args.requests}, 目标 {url}")

    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=args.timeout) as client:
        # 预热 1 发（加载模型/建立连接池）
        warm = await client.post(url, json=payload_fn(0))
        print(f"  预热: HTTP {warm.status_code}, {(time.perf_counter() - start) * 1000:.0f} ms")

        workers = [
            asyncio.create_task(worker(w, client, url, payload_fn, queue, results))
            for w in range(args.concurrency)
        ]
        await asyncio.gather(*workers)

    wall = time.perf_counter() - start

    latencies = sorted(r[0] for r in results)
    errors = [r for r in results if not r[1]]
    ok_count = len(results) - len(errors)

    report = {
        "endpoint": args.endpoint,
        "mode": args.mode if args.endpoint == "search" else None,
        "concurrency": args.concurrency,
        "total_requests": len(results),
        "success": ok_count,
        "errors": len(errors),
        "error_rate": len(errors) / len(results) if results else 0,
        "wall_time_s": round(wall, 2),
        "throughput_rps": round(len(results) / wall, 2),
        "latency_ms": {
            "min": round(latencies[0], 0) if latencies else 0,
            "p50": round(percentile(latencies, 50), 0),
            "p95": round(percentile(latencies, 95), 0),
            "p99": round(percentile(latencies, 99), 0),
            "max": round(latencies[-1], 0) if latencies else 0,
            "mean": round(statistics.mean(latencies), 0) if latencies else 0,
        },
        "p95_under_15s": percentile(latencies, 95) < 15000,
    }

    print(f"\n{'=' * 56}")
    print(f"完成 {len(results)} 请求，成功 {ok_count}，失败 {len(errors)}，耗时 {wall:.1f}s")
    print(f"  吞吐   : {report['throughput_rps']} req/s")
    print(f"  P50    : {report['latency_ms']['p50']:.0f} ms")
    print(f"  P95    : {report['latency_ms']['p95']:.0f} ms")
    print(f"  P99    : {report['latency_ms']['p99']:.0f} ms")
    print(f"  Max    : {report['latency_ms']['max']:.0f} ms")
    verdict = "✅ 通过（P95 < 15s）" if report["p95_under_15s"] else "❌ 未达标（P95 ≥ 15s）"
    print(f"  验收   : {verdict}")

    if errors:
        print("\n错误样例（前 5）:")
        for _, _, err in errors[:5]:
            print(f"  ✗ {err}")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n报告已保存: {out}")

    return 0 if report["p95_under_15s"] else 1


if __name__ == "__main__":
    sys_exit = asyncio.run(main())
    raise SystemExit(sys_exit)
