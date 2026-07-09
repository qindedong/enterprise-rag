# 企业级智能知识库 RAG — 测试计划 (Test Plan)

> **文档版本**: v1.0
> **创建日期**: 2026年7月10日
> **关联文档**: [PRD.md](./PRD.md) | [ARCHITECTURE.md](./ARCHITECTURE.md) | [TASKS.md](./TASKS.md)

---

## 目录

1. [测试策略总览](#1-测试策略总览)
2. [测试工具链](#2-测试工具链)
3. [单元测试计划](#3-单元测试计划)
4. [集成测试计划](#4-集成测试计划)
5. [API 端到端测试计划](#5-api-端到端测试计划)
6. [RAG 准确率测试](#6-rag-准确率测试)
7. [性能测试（Benchmark）](#7-性能测试benchmark)
8. [安全测试](#8-安全测试)
9. [前端测试](#9-前端测试)
10. [测试环境与 CI/CD](#10-测试环境与-cicd)

---

## 1. 测试策略总览

### 1.1 测试金字塔

```
         ╱    E2E 测试    ╲        ← 10%，验证核心用户旅程
        ╱──────────────────╲
       ╱    集成测试         ╲      ← 20%，验证模块间协作、API 契约
      ╱────────────────────────╲
     ╱      单元测试              ╲    ← 70%，验证单个函数/类
    ╱──────────────────────────────╲
```

### 1.2 测试原则

| 原则 | 说明 |
|------|------|
| **测试金字塔** | 70% 单元 + 20% 集成 + 10% E2E，不写反金字塔 |
| **独立性** | 每个测试不依赖其他测试的执行顺序 |
| **可重复** | 同一测试多次运行结果一致（确定性） |
| **快速反馈** | 单元测试 < 30s，集成测试 < 5min |
| **覆盖核心路径** | Happy Path 全覆盖 + 关键异常路径 |
| **Mock 外部依赖** | 单元测试 Mock 所有外部服务（DB/LLM/Embedding/Qdrant） |
| **真实环境集成测试** | 集成测试使用真实 PostgreSQL（测试库）/ Qdrant（测试 Collection） |

### 1.3 各阶段测试目标

| 阶段 | 目标覆盖率 | 通过标准 |
|------|:---:|------|
| Sprint 1 结束 | 基线建立 | pytest 框架就绪，核心工具类有测试 |
| Sprint 2 结束 | Auth > 90%, KB > 85% | 所有 P0 测试通过 |
| Sprint 3 结束 | 解析器 > 85%, 分块器 > 95% | 所有 P0 测试通过 |
| Sprint 5 结束 | 检索模块 > 85% | 所有 P0 测试通过 + Recall@5 基线 |
| Sprint 6 结束 | RAG Pipeline > 85% | 所有 P0 测试通过 + 引用准确率基线 |
| **Sprint 8（MVP）** | **总体 > 80%** | **全部测试通过，无 Skip/XFail** |

---

## 2. 测试工具链

### 2.1 核心工具

| 工具 | 用途 | 版本要求 |
|------|------|---------|
| **pytest** | 测试框架 | ≥ 8.0 |
| **pytest-asyncio** | 异步测试支持 | ≥ 0.23 |
| **pytest-cov** | 覆盖率报告 | ≥ 4.1 |
| **pytest-mock** | Mock 工具 | ≥ 3.12 |
| **httpx** | FastAPI 测试客户端（AsyncClient） | ≥ 0.26 |
| **factory-boy** | 测试数据工厂 | ≥ 3.3 |
| **faker** | 假数据生成 | ≥ 22.0 |
| **aiosqlite** | 测试用内存数据库 | ≥ 0.19 |

### 2.2 Pytest 配置

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--strict-markers",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80",
]
markers = [
    "unit: 单元测试",
    "integration: 集成测试（需要数据库等外部依赖）",
    "e2e: 端到端测试",
    "slow: 运行较慢的测试（>5s）",
    "rag: RAG 准确率测试（需要 LLM 和 Embedding 服务）",
]
```

---

## 3. 单元测试计划

### 3.1 公共基础设施测试

| 模块 | 文件 | 测试重点 | 目标覆盖率 |
|------|------|---------|:---:|
| 异常体系 | `test_exceptions.py` | 各异常类创建、code/message/detail 正确传递 | 100% |
| 全局异常处理器 | `test_exception_handlers.py` | AppException → 统一格式，未知异常 → 500 不泄露 | 100% |
| 响应模型 | `test_response.py` | APIResponse / PageInfo / PaginatedResponse 序列化/反序列化 | 100% |
| 日志 | `test_logger.py` | get_logger 返回 Logger，格式化输出 | 90% |
| 配置 | `test_config.py` | Settings 读取 .env + 默认值 + 类型校验 | 95% |
| JWT 工具 | `test_jwt.py` | encode/decode/expire/invalid 场景 | 100% |
| 密码工具 | `test_security.py` | bcrypt hash/verify/不同密码不同哈希 | 100% |

### 3.2 Service 层测试

| 模块 | 测试重点 | 目标覆盖率 | Mock 对象 |
|------|---------|:---:|---------|
| **AuthService** | register（去重/弱密码/邮箱格式）<br/>login（成功/密码错误/用户不存在）<br/>refresh（有效/过期/篡改） | 95%+ | UserRepository |
| **KBService** | create（名称重复/参数校验）<br/>list（分页/筛选）<br/>update（权限/不存在）<br/>delete（级联检查/权限） | 90%+ | KBRepository |
| **DocumentService** | upload（去重/类型校验）<br/>流程编排（各步骤调用验证）<br/>错误处理（解析失败/Embedding 失败） | 90%+ | DocRepo, ChunkRepo, Parser, EmbeddingClient, QdrantClient |
| **ConversationService** | create/list/detail/delete<br/>权限校验 | 85%+ | ConversationRepository |
| **SearchService** | 调用 RetrievalPipeline，参数传递正确 | 85%+ | RetrievalPipeline |

### 3.3 Repository 层测试

Repository 使用 **SQLite 内存数据库** 测试（aiosqlite），不依赖真实 PostgreSQL。

| 模块 | 测试重点 | 目标覆盖率 |
|------|---------|:---:|
| **UserRepository** | create / findByEmail / findByUsername / list 分页 | 90%+ |
| **KBRepository** | CRUD / 按 owner 查询 / 成员管理 / 统计 | 90%+ |
| **DocumentRepository** | CRUD / 去重 / 状态筛选 / 分页 | 90%+ |
| **ChunkRepository** | bulk_insert / 按文档查询 / 级联删除 | 90%+ |
| **ConversationRepository** | CRUD / 按用户查询 / 按 KB 查询 | 85%+ |

### 3.4 AI 模块单元测试

| 模块 | 测试重点 | 目标覆盖率 | Mock 对象 |
|------|---------|:---:|---------|
| **PDFParser** | 正常 PDF / 加密 PDF / 空 PDF / 损坏 PDF | 90%+ | - |
| **MarkdownParser** | 标题层级保留 / 代码块 / 空文件 | 90%+ | - |
| **TextSplitter** | chunk_size=500 / overlap=100 / 边界情况 / 空文本 | 95%+ | - |
| **TokenCounter** | 中文 / 英文 / 混合 / 空文本 | 95%+ | - |
| **QueryRewriter** | 口语→正式 / 简写→全称 / 空输入 | 85%+ | LLMClient |
| **Reranker** | 50→10 / 分数排序 / 空输入 | 85%+ | - |
| **DiversityFilter** | 重复文档去重 / threshold=0.95 / 空列表 | 90%+ | - |
| **PromptBuilder** | Context 截断 / 格式化 / 编号正确 | 90%+ | - |
| **CitationValidator** | 引用在 Context 中存在/不存在 / 无引用回答 | 95%+ | - |

---

## 4. 集成测试计划

### 4.1 数据库集成测试

使用真实的 **PostgreSQL 测试数据库**（Docker）。

| 场景 | 测试内容 | 验证点 |
|------|---------|--------|
| Alembic 迁移 | upgrade head → downgrade base → upgrade head | 迁移可逆、幂等 |
| 事务回滚 | Service 抛异常 → 数据未写入 | 事务边界正确 |
| 并发写入 | 2 个协程同时创建同名用户 | 唯一约束生效 |
| 级联删除 | 删除 KB → 级联删除 Member/Document/Chunk | 外键约束生效 |
| JSONB 查询 | metadata 字段增删改查 | Query/Index 正确 |

### 4.2 API 集成测试

使用 `httpx.AsyncClient` 测试真实 FastAPI 应用（不 Mock）。

| 场景 | 测试步骤 | 预期结果 |
|------|---------|---------|
| **注册→登录→访问** | 注册 → 登录获取 Token → 用 Token 访问受保护接口 | 200 + 数据 |
| **Token 过期** | 使用过期 Token 访问 | 401 + "登录已过期" |
| **Token 刷新** | 登录 → 用 refresh_token 获取新 access_token | 200 + 新 Token |
| **创建 KB→上传文档** | 创建 KB → 上传 PDF → 轮询状态 → completed | 全链路 200 |
| **上传重复文档** | 上传文档 → 再次上传相同内容 → 409 | 去重生效 |
| **上传不支持格式** | 上传 .exe 文件 | 422 + "不支持的文件类型" |
| **空知识库提问** | 在无文档的 KB 中提问 | 400 + "该知识库中暂无文档" |
| **权限校验** | 用户 A 尝试删除用户 B 的知识库 | 403 |
| **不存在的资源** | 访问不存在的 KB ID | 404 |
| **分页** | 创建 25 个 KB → 请求 page=2, page_size=10 | 返回 10 条，total=25 |

### 4.3 Qdrant 集成测试

使用 **Qdrant 测试 Collection**。

| 场景 | 测试内容 | 验证点 |
|------|---------|--------|
| upsert + search | 写入 100 条向量 → 检索 | Top-K 排序正确，Payload 完整 |
| 过滤检索 | 按 kb_id 过滤检索 | 只返回匹配 KB 的文档 |
| delete_points | 按 filter 删除 → 检索 | 已删除的内容不再返回 |
| 向量同步 | 删除 PG Chunk → Qdrant Point 同步删除 | 两边数据一致 |

---

## 5. API 端到端测试计划

### 5.1 完整用户旅程（Happy Path）

```
用户注册 → 登录 → 创建知识库 → 上传 3 份文档（PDF/MD/TXT）
  → 等待处理完成 → 提问"公司年假有多少天？"
  → 收到流式回答 + 引用 → 追问"怎么申请？"
  → 查看对话历史 → 对第 1 个回答点踩
```

**验证点**：
1. 所有 HTTP 状态码均为 2xx
2. 回答中包含"年假"相关内容
3. 引用列表不为空（citations.length > 0）
4. 引用编号在回答中可找到（如 `[1]`）
5. 对话历史包含 4 条消息（2 问 2 答）
6. 反馈提交成功

### 5.2 异常路径测试

| 场景 | 测试步骤 | 预期结果 |
|------|---------|---------|
| 上传损坏 PDF | 上传一个内容损坏的 PDF → 等待处理 | status=failed, error_message 不为空 |
| LLM 超时 | Mock LLM 超时 → 提问 | 返回 502 + 降级信息 |
| 大文件上传 | 上传 > 100MB 文件 | 413 |
| 高频请求 | 循环 31 次提问 | 第 31 次返回 429 |
| 空问题 | 提交 question="" | 422 |

---

## 6. RAG 准确率测试

### 6.1 检索效果评估

#### 标注数据集

准备 **20+ 个查询**，每条标注 3-5 个相关文档 Chunk：

```python
ANNOTATED_QUERIES = [
    {
        "query": "公司年假有多少天？",
        "kb_id": "kb-hr-policy",
        "relevant_chunk_ids": ["chunk-001", "chunk-005", "chunk-012"],
    },
    {
        "query": "加班费怎么算？",
        "kb_id": "kb-hr-policy",
        "relevant_chunk_ids": ["chunk-020", "chunk-021"],
    },
    # ... 20+ 条
]
```

#### 评估指标

| 指标 | 计算方式 | 目标值 |
|------|---------|:---:|
| **Recall@5** | 在 Top-5 结果中命中的相关 Chunk 数 / 总相关 Chunk 数 | ≥ 90% |
| **Recall@10** | 同上，取 Top-10 | ≥ 95% |
| **MRR** | Mean Reciprocal Rank（第一个相关文档的排名倒数的均值） | ≥ 0.8 |
| **Hit Rate** | 查询中至少命中一个相关 Chunk 的比例 | ≥ 95% |
| **NDCG@10** | 归一化折损累计增益 | ≥ 0.85 |

#### 评估执行

```bash
# 每次检索策略变更后执行
pytest tests/rag/test_retrieval_accuracy.py -m rag -v

# 输出示例：
# Recall@5: 0.92 ✅
# MRR: 0.85 ✅
# Hit Rate: 0.96 ✅
```

### 6.2 生成效果评估

#### 评估方法

| 方法 | 说明 | 频率 |
|------|------|------|
| **人工评估** | 每次 Sprint Review 抽 10 个回答人工打分（1-5 分） | 每 Sprint |
| **LLM-as-Judge** | 使用另一个 LLM 自动评估（Faithfulness / Relevance） | 每次代码变更 |
| **用户反馈** | 线上点赞/点踩率 | 持续 |

#### 评估指标

| 指标 | 说明 | 目标值 |
|------|------|:---:|
| **Faithfulness（忠实度）** | 回答是否 100% 基于 Context（无幻觉） | ≥ 95% |
| **Answer Relevance** | 回答是否切题 | ≥ 90% |
| **Citation Precision** | 每个引用是否确实支持对应声明 | ≥ 98% |
| **Citation Recall** | 每个事实声明是否都有引用 | ≥ 90% |

#### LLM-as-Judge Prompt

```python
FAITHFULNESS_PROMPT = """你是一个严格的答案忠实度评估器。

请判断以下 AI 回答是否完全基于「参考资料」中的内容：

参考资料：
{context}

AI 回答：
{answer}

评估标准：
- 如果回答中的每个事实声明都能在参考资料中找到原文支持 → "faithful"
- 如果回答中包含参考资料中没有的信息（哪怕是常识）→ "unfaithful"
- 如果回答说"根据现有资料无法回答"且确实资料中无相关信息 → "faithful"

请返回 JSON：
{"verdict": "faithful" | "unfaithful", "hallucinations": ["编造的内容"], "score": 0-100}
"""
```

### 6.3 引用准确性测试

```python
def test_citation_accuracy():
    """自动化引用准确性测试"""
    for test_case in CITATION_TEST_CASES:
        answer, citations, context_docs = test_case
        
        # 1. 提取回答中的所有引用编号
        cited_nums = set(re.findall(r'\[(\d+)\]', answer))
        available_nums = set(c.index for c in citations)
        
        # 2. 验证引用编号存在
        assert cited_nums.issubset(available_nums), \
            f"回答中引用了不存在的编号: {cited_nums - available_nums}"
        
        # 3. 验证引用内容在 context 中
        for citation in citations:
            found = any(citation.content_snippet in doc.content for doc in context_docs)
            assert found, f"引用 [{citation.index}] 的内容在 context 中找不到"
```

---

## 7. 性能测试（Benchmark）

### 7.1 测试场景

| 场景 | 并发用户 | 持续时间 | 目标指标 |
|------|:---:|:---:|------|
| **文档上传** | 10 | 5min | P95 < 5s（不含向量化后台处理） |
| **向量检索** | 50 QPS | 5min | P95 < 500ms |
| **RAG 问答（非流式）** | 20 | 10min | P95 < 15s（含 LLM 生成） |
| **RAG 问答（流式）** | 20 | 10min | TTFB（首字节）< 2s |
| **知识库列表** | 100 | 5min | P95 < 200ms |
| **混合负载** | 50 | 10min | 错误率 < 0.1% |

### 7.2 性能测试脚本

```python
# tests/benchmark/test_performance.py
import asyncio
import time
import statistics
import httpx

async def benchmark_rag_query(concurrent_users: int = 20, duration_seconds: int = 600):
    """RAG 问答性能测试"""
    latencies = []
    errors = 0
    
    async def single_query(client: httpx.AsyncClient):
        start = time.time()
        try:
            response = await client.post(
                "/api/v1/knowledge-bases/test-kb/chat/sync",
                json={"question": "公司年假有多少天？"},
                timeout=30,
            )
            if response.status_code != 200:
                nonlocal errors
                errors += 1
        except Exception:
            errors += 1
        finally:
            latencies.append(time.time() - start)
    
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        end_time = time.time() + duration_seconds
        tasks = []
        while time.time() < end_time:
            if len(tasks) >= concurrent_users:
                await asyncio.gather(*tasks)
                tasks = []
            tasks.append(single_query(client))
    
    # 计算指标
    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    
    print(f"总请求: {len(latencies)}, 错误: {errors}")
    print(f"P50: {p50:.2f}s, P95: {p95:.2f}s, P99: {p99:.2f}s")
    
    assert p95 < 15, f"P95 延迟 {p95:.2f}s 超过目标 15s"
```

### 7.3 性能基线

| 指标 | MVP 目标 | Sprint 8 验证 |
|------|:---:|:---:|
| API P95 延迟（简单查询） | < 200ms | ✅ |
| 检索 P95 延迟 | < 2s | ✅ |
| RAG 问答 P95 延迟 | < 15s | ✅ |
| 100 并发错误率 | < 0.1% | ✅ |
| 每小时可处理文档数 | > 50 | ✅ |

---

## 8. 安全测试

### 8.1 安全测试清单

| 类别 | 测试项 | 测试方法 | 预期结果 |
|------|--------|---------|---------|
| **SQL 注入** | 在搜索参数中输入 `'; DROP TABLE users; --` | API 测试 | 参数化查询防止注入，无异常 |
| **XSS** | 文档标题设为 `<script>alert('xss')</script>` | API + 前端 | 输出已被编码，不执行脚本 |
| **JWT 篡改** | 修改 JWT Payload 中的 user_id | API 测试 | 签名验证失败，返回 401 |
| **越权访问** | 用户 A 访问用户 B 的知识库文档 | API 测试 | 返回 403 |
| **越权删除** | 用户 A 尝试删除用户 B 的知识库 | API 测试 | 返回 403 |
| **Token 重放** | 同一 Token 在高并发下重复使用 | API 测试 | 所有请求正常，无副作用 |
| **大文件上传** | 上传 500MB 文件 | API 测试 | 返回 413（nginx client_max_body_size） |
| **恶意文件** | 上传伪装成 PDF 的 .exe 文件 | API 测试 | MIME 类型校验，拒绝 |
| **敏感信息泄露** | 触发异常，检查返回内容 | API 测试 | 不暴露数据库 URL / API Key / 堆栈信息 |
| **日志脱敏** | 检查日志文件 | 日志审查 | 无密码/Token/API Key 明文 |

### 8.2 安全扫描工具

```bash
# Bandit — Python 安全漏洞静态扫描
pip install bandit
bandit -c pyproject.toml -r app/

# Safety — 依赖库漏洞检查
pip install safety
safety check

# 手动审查
# - 所有数据库查询是否使用参数化
# - 所有文件操作是否校验路径
# - 所有外部输入是否经过 Pydantic 校验
```

---

## 9. 前端测试

### 9.1 测试工具

| 工具 | 用途 |
|------|------|
| **Vitest** | 组件单元测试 |
| **React Testing Library** | 组件渲染和行为测试 |
| **Playwright** | E2E 浏览器测试 |
| **MSW (Mock Service Worker)** | Mock API 响应 |

### 9.2 前端测试清单

| 类别 | 测试内容 | 工具 |
|------|---------|------|
| 组件单元测试 | 登录表单校验、注册表单校验 | Vitest + RTL |
| 组件单元测试 | 分页组件、状态标签组件 | Vitest + RTL |
| 集成测试 | AuthContext 状态管理（登录/登出/Token 刷新） | Vitest + MSW |
| 集成测试 | 文档上传组件（拖拽、进度条） | Vitest + MSW |
| E2E | 登录 → 知识库列表 → 创建 KB → 上传文档 | Playwright |
| E2E | 知识库 → 问答 → 流式显示 → 查看引用 | Playwright |
| E2E | 对话历史 → 切换对话 → 反馈 | Playwright |

---

## 10. 测试环境与 CI/CD

### 10.1 测试环境

| 环境 | 数据库 | Qdrant | 用途 |
|------|--------|--------|------|
| **本地** | SQLite 内存 / Docker PG | Docker Qdrant | 开发阶段单元测试 + 集成测试 |
| **CI** | Docker PG（临时容器） | Docker Qdrant（临时容器） | 自动化测试流水线 |
| **预发布** | 独立 PG 实例 | 独立 Qdrant Collection | 性能测试 + 准确率测试 |

### 10.2 CI/CD 测试流水线

```yaml
# .github/workflows/test.yml
name: Test

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install black ruff mypy
      - run: black --check app/ tests/
      - run: ruff check app/ tests/
      - run: mypy app/

  unit-test:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: { POSTGRES_USER: test, POSTGRES_PASSWORD: test, POSTGRES_DB: testdb }
      qdrant:
        image: qdrant/qdrant:latest
      redis:
        image: redis:7-alpine
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e ".[dev]"
      - run: pytest tests/unit/ -v --cov=app --cov-report=xml
      - run: pytest tests/integration/ -v -m "not slow"

  e2e-test:
    runs-on: ubuntu-latest
    needs: unit-test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - run: docker compose -f docker-compose.test.yml up -d
      - run: pytest tests/e2e/ -v
      - run: docker compose -f docker-compose.test.yml down
```

### 10.3 覆盖率报告

```bash
# 生成 HTML 覆盖率报告
pytest --cov=app --cov-report=html

# 查看缺失行
pytest --cov=app --cov-report=term-missing

# 失败阈值（低于 80% 构建失败）
pytest --cov=app --cov-fail-under=80
```

---

### 10.4 测试运行速查

```bash
# 运行所有测试
pytest

# 只运行单元测试
pytest -m unit

# 只运行集成测试
pytest -m integration

# 跳过慢速测试
pytest -m "not slow"

# 运行特定模块
pytest tests/unit/services/test_auth_service.py -v

# 运行特定测试
pytest tests/unit/services/test_auth_service.py::TestAuthService::test_register_success -v

# 并行运行（需要 pytest-xdist）
pytest -n auto

# 只运行上次失败的测试
pytest --lf

# 覆盖率报告
pytest --cov=app --cov-report=html && open htmlcov/index.html
```

---

> **下一步**: 阅读 [部署文档 (DEPLOYMENT.md)](./DEPLOYMENT.md) 了解部署方案。
