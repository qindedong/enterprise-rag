"""
性能压测 — 脚本版（无需 Web UI，直接输出结果）

用法:
    cd backend
    python perf/run_load_test.py
"""
import collections
import json
import subprocess
import sys
import time


def run_locust_headless(users: int, run_time: str) -> dict:
    """运行 locust headless 模式并解析结果"""
    cmd = [
        sys.executable,
        "-m",
        "locust",
        "-f",
        "perf/locustfile.py",
        "--host=http://127.0.0.1:8000",
        f"--users={users}",
        f"--run-time={run_time}",
        "--spawn-rate=10",
        "--headless",
        "--only-summary",
    ]
    print(f"\n{'=' * 60}")
    print(f"运行 {users} 并发压测，持续 {run_time}...")
    print("=" * 60)

    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr[:1000])

    return {"users": users, "run_time": run_time}


def main():
    print("RAG 系统性能压测")
    print(f"目标: http://127.0.0.1:8000")

    # 轻量级测试
    run_locust_headless(10, "30s")
    time.sleep(3)

    # 中等负载
    run_locust_headless(50, "30s")
    time.sleep(3)

    # 高负载（100 并发）
    run_locust_headless(100, "30s")

    print("\n压测完成")
    print("详细报告: locust -f perf/locustfile.py --host=http://127.0.0.1:8000")


if __name__ == "__main__":
    main()
