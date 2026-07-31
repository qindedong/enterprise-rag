# -*- coding: utf-8 -*-
"""Sprint 8.1 前后端全链路联调 — 12 个 P0 User Story 冒烟验证脚本.

对运行中的本地全栈（API :8000 / PostgreSQL / Qdrant / Redis）逐条验证
PRD.md 第 9 节的 12 个 P0 用户故事。可重复执行：每次使用带时间戳的
独立用户与知识库，结束后自动清理测试数据。

用法:
    backend/.venv/Scripts/python.exe scripts/e2e_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

BASE = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
API = f"{BASE}/api/v1"
TS = int(time.time())
EMAIL = f"smoke_{TS}@example.com"
PASSWORD = "SmokeTest123!"
DOC_PATH = Path(__file__).resolve().parent.parent / "test-data" / "公司考勤制度.md"

results: list[tuple[str, bool, str]] = []


def unwrap(r: requests.Response):
    """解开统一响应包装 {code, message, data}，返回 data（无包装则原样返回）."""
    body = r.json()
    if isinstance(body, dict) and "data" in body and "code" in body:
        return body["data"]
    return body


def items_of(data) -> list:
    """从分页/列表数据中提取条目列表."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("items", "results", "data"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


def check(us: str, ok: bool, detail: str = "") -> None:
    results.append((us, ok, detail))
    mark = "✅" if ok else "❌"
    print(f"{mark} {us} {detail}")


def main() -> int:
    s = requests.Session()

    # ---- 健康检查（前置条件）------------------------------------------
    r = s.get(f"{BASE}/health", timeout=10).json()
    assert r["status"] == "healthy" and all(r["checks"].values()), r
    print(f"服务健康: {r['checks']}\n")

    # ---- US-11 用户注册与登录 -----------------------------------------
    r = s.post(f"{API}/auth/register", json={
        "username": f"smoke_{TS}", "email": EMAIL, "password": PASSWORD,
        "display_name": "Smoke Tester",
    }, timeout=15)
    check("US-11a 注册", r.status_code in (200, 201), f"HTTP {r.status_code}")

    r = s.post(f"{API}/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=15)
    login_data = unwrap(r)
    ok = r.status_code == 200 and "access_token" in login_data
    check("US-11b 登录签发 JWT", ok, f"HTTP {r.status_code}")
    token = login_data["access_token"]
    s.headers.update({"Authorization": f"Bearer {token}"})

    r = s.get(f"{API}/auth/me", timeout=15)
    check("US-11c 获取当前用户", r.status_code == 200 and unwrap(r)["email"] == EMAIL)

    # ---- US-08 多知识库管理 -------------------------------------------
    r = s.post(f"{API}/knowledge-bases", json={
        "name": f"冒烟测试库 {TS}", "description": "e2e smoke",
    }, timeout=15)
    ok = r.status_code in (200, 201)
    kb = unwrap(r)
    kb_id = kb.get("id")
    check("US-08a 创建知识库", ok and kb_id, f"HTTP {r.status_code} id={kb_id}")

    r = s.get(f"{API}/knowledge-bases", timeout=15)
    names = [k["name"] for k in items_of(unwrap(r))]
    check("US-08b 知识库列表", any(f"冒烟测试库 {TS}" in n for n in names), f"共 {len(names)} 个库")

    # ---- US-06 上传文档自动处理 ---------------------------------------
    with open(DOC_PATH, "rb") as f:
        r = s.post(f"{API}/knowledge-bases/{kb_id}/documents",
                   files={"file": (DOC_PATH.name, f, "text/markdown")}, timeout=60)
    ok = r.status_code in (200, 201, 202)
    doc = unwrap(r)
    doc_id = doc.get("id")
    check("US-06 上传文档", ok and doc_id, f"HTTP {r.status_code} 初始状态={doc.get('status')}")

    # ---- US-07 文档状态跟踪（轮询至 completed）-------------------------
    status, waited = "unknown", 0
    for _ in range(60):
        r = s.get(f"{API}/knowledge-bases/{kb_id}/documents", timeout=15)
        docs = items_of(unwrap(r))
        mine = next((d for d in docs if d["id"] == doc_id), None)
        if mine:
            status = mine["status"]
            if status in ("completed", "failed"):
                break
        time.sleep(2)
        waited += 2
    check("US-07 文档处理完成", status == "completed", f"status={status} 等待 {waited}s")

    # ---- US-09 知识库统计 ----------------------------------------------
    r = s.get(f"{API}/knowledge-bases/{kb_id}", timeout=15)
    kb_detail = unwrap(r)
    stats = kb_detail.get("stats", kb_detail)
    doc_count = stats.get("document_count", stats.get("doc_count"))
    check("US-09 知识库统计", r.status_code == 200 and (doc_count or 0) >= 1,
          f"document_count={doc_count}")

    # ---- US-01 / US-05 自然语言问答 + 引用溯源（非流式）------------------
    question = "公司考勤制度中，迟到是怎么规定的？"
    r = s.post(f"{API}/knowledge-bases/{kb_id}/chat/sync",
               json={"question": question}, timeout=120)
    ans = unwrap(r) if r.status_code == 200 else {}
    answer = ans.get("answer", "")
    citations = ans.get("citations", ans.get("sources", []))
    check("US-01 自然语言问答", r.status_code == 200 and len(answer) > 10,
          f"回答 {len(answer)} 字")
    check("US-05 引用溯源", bool(citations), f"{len(citations)} 条引用")

    # ---- US-04 诚实回答（知识库外问题应拒答/提示无相关内容）-------------
    r = s.post(f"{API}/knowledge-bases/{kb_id}/chat/sync",
               json={"question": "火星上最高的山叫什么名字？"}, timeout=120)
    off = (unwrap(r) or {}).get("answer", "") if r.status_code == 200 else ""
    honest = any(k in off for k in ("没有", "无法", "未找到", "不清楚", "不包含", "没有相关", "抱歉"))
    check("US-04 诚实回答", r.status_code == 200 and honest, f"回答前 40 字: {off[:40]!r}")

    # ---- US-02 流式回答（SSE）------------------------------------------
    r = s.post(f"{API}/knowledge-bases/{kb_id}/chat",
               json={"question": question}, stream=True, timeout=120)
    events, got_done = [], False
    if r.status_code == 200:
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                payload = line[5:].strip()
                events.append(payload)
                if payload == "[DONE]" or '"done"' in payload or '"type": "done"' in payload.replace(" ", ""):
                    got_done = True
    check("US-02 流式回答", r.status_code == 200 and len(events) > 1,
          f"{len(events)} 个 SSE 事件, done={got_done}")

    # ---- US-03 多轮对话追问 --------------------------------------------
    r = s.post(f"{API}/knowledge-bases/{kb_id}/conversations",
               params={"question": question}, timeout=15)
    conv = unwrap(r) or {}
    conv_id = conv.get("id", conv.get("conversation_id"))
    ok = r.status_code in (200, 201) and conv_id
    check("US-03a 创建对话", ok, f"HTTP {r.status_code}")

    r1 = s.post(f"{API}/knowledge-bases/{kb_id}/chat/sync",
                json={"question": question, "conversation_id": conv_id}, timeout=120)
    r2 = s.post(f"{API}/knowledge-bases/{kb_id}/chat/sync",
                json={"question": "那早退呢？", "conversation_id": conv_id}, timeout=120)
    follow = (unwrap(r2) or {}).get("answer", "") if r2.status_code == 200 else ""
    check("US-03b 追问上下文理解", r2.status_code == 200 and len(follow) > 10,
          f"追问回答 {len(follow)} 字")

    r = s.get(f"{API}/conversations/{conv_id}/messages", timeout=15)
    msgs = items_of(unwrap(r))
    check("US-03c 历史消息持久化", r.status_code == 200 and len(msgs) >= 4,
          f"{len(msgs)} 条消息")

    # ---- US-10 文档删除同步 --------------------------------------------
    r = s.delete(f"{API}/documents/{doc_id}", timeout=30)
    check("US-10a 删除文档", r.status_code in (200, 204), f"HTTP {r.status_code}")
    time.sleep(2)
    r = s.post(f"{API}/knowledge-bases/{kb_id}/search",
               json={"question": "迟到规定", "top_k": 5}, timeout=30)
    hits = items_of(unwrap(r)) if r.status_code == 200 else []
    remaining = [h for h in hits
                 if h.get("document_id", h.get("doc_id")) == doc_id]
    check("US-10b 向量同步删除", r.status_code == 200 and not remaining,
          f"删除后剩余命中 {len(remaining)} 条")

    # ---- US-12 系统监控（分析面板 + 健康检查）-----------------------------
    r = s.get(f"{API}/analytics/overview", timeout=15)
    check("US-12 系统监控面板", r.status_code == 200, f"HTTP {r.status_code}")

    # ---- 清理：删除测试知识库 -------------------------------------------
    r = s.delete(f"{API}/knowledge-bases/{kb_id}", timeout=30)
    print(f"\n清理测试知识库: HTTP {r.status_code}")

    # ---- 汇总 -----------------------------------------------------------
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n===== 结果: {passed}/{len(results)} 项通过 =====")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
