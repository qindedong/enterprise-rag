# 企业级智能知识库 RAG — 开发路线图 (Roadmap)

> **文档版本**: v1.0
> **创建日期**: 2026年7月10日
> **关联文档**: [PRD.md](./PRD.md) | [TASKS.md](./TASKS.md) | [ARCHITECTURE.md](./ARCHITECTURE.md)

---

## 目录

1. [版本规划概览](#1-版本规划概览)
2. [Definition of Done（完成定义）](#2-definition-of-done完成定义)
3. [Sprint 1-8：MVP 详细规划](#3-sprint-1-8mvp-详细规划)
4. [Sprint 9-16：v1.5 / v2.0 概要规划](#4-sprint-9-16v15--v20-概要规划)
5. [里程碑节点](#5-里程碑节点)
6. [风险识别与应对](#6-风险识别与应对)

---

## 1. 版本规划概览

```
v0.1 项目骨架      v0.2 文档引擎      v0.3 RAG检索      v0.4 RAG生成      v1.0 MVP
  Sprint 1-2         Sprint 3-4        Sprint 5          Sprint 6-7        Sprint 8
    (4周)              (4周)             (2周)              (4周)             (2周)
      ↓                  ↓                 ↓                  ↓                ↓
   基础设施          文档处理管线      检索链路打通        LLM+引用+流式     部署+发布
```

### 版本路线图

| 版本 | Sprint | 时间 | 主题 | 核心目标 |
|------|--------|------|------|---------|
| v0.1 | 1-2 | 第 1-4 周 | **项目骨架** | 项目初始化 + 核心基础设施 + 用户认证 |
| v0.2 | 3-4 | 第 5-8 周 | **文档引擎** | 文档上传 → 解析 → 分块 → 向量化 → Qdrant |
| v0.3 | 5 | 第 9-10 周 | **RAG 检索** | 查询改写 + 向量检索 + 重排序 |
| v0.4 | 6-7 | 第 11-14 周 | **RAG 生成** | LLM 调用 + Prompt + 流式 + 引用 |
| **v1.0 MVP** | **8** | **第 15-16 周** | **MVP 发布** | 前端集成 + 联调 + Docker 部署 + 文档 |
| v1.5 | 9-12 | 第 17-24 周 | **增强版** | 混合检索 + RBAC + 多轮对话 + 反馈 |
| v2.0 | 13-16 | 第 25-32 周 | **企业版** | 跨知识库 + 分析面板 + SSO + K8s |

**总周期：32 周（约 8 个月）到达 v2.0。**

---

## 2. Definition of Done（完成定义）

### 2.1 每个 Sprint 交付标准

每个 Sprint 结束时，以下所有条件必须同时满足：

- [ ] ✅ **所有单元测试通过**（覆盖率 ≥ 80%）
- [ ] ✅ **所有 API 集成测试通过**
- [ ] ✅ **Black 格式化检查通过**（`black --check .`）
- [ ] ✅ **Ruff Lint 检查通过**（`ruff check .`）
- [ ] ✅ **MyPy 类型检查通过**（`mypy app/`）
- [ ] ✅ **Docker Compose 一键启动成功**（所有服务 healthy）
- [ ] ✅ **相关文档已更新**（API.md / DATABASE.md / CHANGELOG.md）
- [ ] ✅ **Code Review 完成**（参考 review.md 检查清单）
- [ ] ✅ **所有 P0 Bug 已修复**（Release Blocker 清零）
- [ ] ✅ **Sprint 回顾已完成**（What went well / What didn't / Action items）

### 2.2 每个 Task 交付标准

- 代码通过 Black + Ruff + MyPy
- 单元测试覆盖核心路径
- 公共函数有 Google Docstring
- 没有 `# TODO`（要么完成，要么创建新的 Task 跟踪）

---

## 3. Sprint 1-8：MVP 详细规划

---

### Sprint 1：项目初始化与基础设施

| 维度 | 详情 |
|------|------|
| **时间** | 第 1-2 周 |
| **目标** | 搭建完整开发环境、建立 CI/CD 流水线、实现核心基础设施 |
| **主题** | 打好地基，确保后续 Sprint 能高效运转 |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 项目结构 | 完整目录结构 | 符合 ARCHITECTURE.md 定义的 DDD 分层目录 |
| 配置 | pyproject.toml | Black + Ruff + MyPy + Pytest 配置 |
| 配置 | Pydantic Settings | 7 个配置类（App/DB/Redis/LLM/Embed/Qdrant/Security） |
| 配置 | .env.template | 所有环境变量模板，含注释说明 |
| 核心 | 统一异常体系 | 7 个异常子类 + 全局异常处理器 |
| 核心 | 统一日志 | get_logger()、结构化输出、级别控制 |
| 核心 | 统一响应模型 | APIResponse + PaginatedResponse + PageInfo |
| 数据库 | Alembic 初始化 | alembic.ini + env.py，initial migration |
| 数据库 | Docker Compose | PostgreSQL 16 + Qdrant + Redis 三服务 |
| API | FastAPI 应用入口 | main.py，注册中间件和异常处理器 |
| API | 健康检查 | GET /health（检查 DB + Redis + Qdrant） |
| API | CORS 中间件 | 开发环境允许 localhost:3000 |
| CI/CD | GitHub Actions | PR 自动运行 Black + Ruff + MyPy + Pytest |
| 测试 | 基础单元测试 | 异常处理器、响应模型测试 |

**Sprint 1 依赖关系**：

```
创建目录结构
    ↓
pyproject.toml → .env.template → Pydantic Settings
    ↓
异常体系 ← → 统一日志 ← → 统一响应模型
    ↓
SQLAlchemy 引擎 → Alembic 初始化
    ↓
Docker Compose → FastAPI 入口 + 健康检查 + CORS
    ↓
CI Pipeline → 基础单元测试
```

---

### Sprint 2：认证与知识库管理

| 维度 | 详情 |
|------|------|
| **时间** | 第 3-4 周 |
| **目标** | 实现完整的用户系统 + 知识库 CRUD + 基础权限 |
| **主题** | 让"人"能进来，让"资源"能管理 |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 数据库 | users 表 Migration | PostgreSQL 中创建 users 表 |
| 数据库 | knowledge_bases 表 Migration | 创建知识库表 |
| 数据库 | kb_members 表 Migration | 创建成员关联表 |
| ORM 模型 | User / KB / KBMember | SQLAlchemy 模型定义 |
| Repository | UserRepository | 用户 CRUD + 按邮箱/用户名查询 |
| Repository | KBRepository | 知识库 CRUD + 成员管理 + 统计 |
| 工具 | 密码哈希 | bcrypt hash/verify |
| 工具 | JWT Token | 生成/验证 access_token + refresh_token |
| Service | AuthService | 注册/登录/刷新 Token/获取当前用户 |
| Service | KBService | 知识库 CRUD + 权限校验 |
| API | POST /auth/register | 用户注册 |
| API | POST /auth/login | 用户登录 |
| API | POST /auth/refresh | Token 刷新 |
| API | GET /auth/me | 当前用户信息 |
| API | POST /kb | 创建知识库 |
| API | GET /kb | 知识库列表（分页） |
| API | GET /kb/{id} | 知识库详情（含统计） |
| API | PUT /kb/{id} | 更新知识库 |
| API | DELETE /kb/{id} | 删除知识库 |
| API | POST /kb/{id}/members | 添加成员 |
| 中间件 | AuthMiddleware | JWT 验证 + get_current_user 注入 |
| 测试 | 认证模块单元测试 | 注册/登录/Token 刷新/异常路径 |
| 测试 | 知识库模块单元测试 | CRUD + 权限 + 边界条件 |

---

### Sprint 3：文档处理管线

| 维度 | 详情 |
|------|------|
| **时间** | 第 5-6 周 |
| **目标** | 实现文档从上传到向量化的完整离线管线 |
| **主题** | 文档"活"起来——上传后自动变成可检索的知识 |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 数据库 | documents 表 Migration | 文档表 |
| 数据库 | document_chunks 表 Migration | 分块表 |
| ORM 模型 | Document / DocumentChunk | |
| Repository | DocumentRepository | CRUD + 去重 + 状态查询 |
| Repository | ChunkRepository | 批量插入 + 按文档查询 |
| 解析器 | BaseParser 抽象接口 | 定义 parse() 统一接口 |
| 解析器 | PDFParser | PyMuPDF 提取文字 |
| 解析器 | MarkdownParser | 按标题层级解析 |
| 解析器 | TextParser | 纯文本解析 |
| 解析器 | ParserRegistry | 根据文件类型选择解析器 |
| 分块器 | TextSplitter | RecursiveCharacterTextSplitter（500/100） |
| 分块器 | TokenCounter | tiktoken 精确计数 |
| 分块器 | validate_chunks() | 分块质量校验 |
| 基础设施 | EmbeddingClient | OpenAI Compatible API 封装 |
| 基础设施 | QdrantClient | 向量 upsert/delete/search |
| Service | DocumentService | 上传编排：解析→分块→向量化→入库 |
| Worker | 异步任务处理 | 后台处理文档，不阻塞 API |
| API | POST /kb/{id}/documents | 上传文档 |
| API | GET /kb/{id}/documents | 文档列表（分页+筛选） |
| API | GET /documents/{id} | 文档详情（含 Chunk 列表） |
| API | DELETE /documents/{id} | 删除文档 + 同步清理 Qdrant |
| API | POST /documents/{id}/reprocess | 重新处理失败文档 |
| 测试 | 解析器单元测试 | 各格式解析正确性 |
| 测试 | 分块器单元测试 | 分块大小/重叠/边界 |
| 测试 | DocumentService 集成测试 | 端到端上传→处理→检索 |

---

### Sprint 4：文档管理与前端基础

| 维度 | 详情 |
|------|------|
| **时间** | 第 7-8 周 |
| **目标** | 完善文档管理 + 前端项目搭建 + 核心页面 |
| **主题** | 有前端能用了——虽然还不完整 |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 后端 | 文档搜索/筛选 API | 按状态、类型、关键词搜索 |
| 后端 | 知识库统计 API | 文档数/Chunk数/问答数 |
| 后端 | 知识库成员管理 API | 添加/移除/修改角色 |
| 前端 | React + TypeScript 项目初始化 | Vite + React Router + TailwindCSS |
| 前端 | API Client 封装 | axios + 拦截器（Token 自动附加） |
| 前端 | 登录/注册页面 | 表单校验 + Token 存储 |
| 前端 | 知识库列表页面 | 卡片展示 + 创建弹窗 |
| 前端 | 知识库详情页面 | 文档列表 + 上传按钮 |
| 前端 | 文档上传组件 | 拖拽上传 + 进度条 |
| 测试 | 文档 API 集成测试 | 上传→状态轮询→列表→删除 |

---

### Sprint 5：RAG 检索链路

| 维度 | 详情 |
|------|------|
| **时间** | 第 9-10 周 |
| **目标** | 实现查询改写 + 向量检索 + 重排序 |
| **主题** | 从"有文档"到"能找到" |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| RAG | QueryRewriter | LLM-based 查询改写 |
| RAG | QdrantRetriever | 封装 Qdrant search API |
| RAG | Reranker | bge-reranker-v2-m3 Cross-Encoder |
| RAG | DiversityFilter | MMR / 相似度去重（threshold=0.95） |
| RAG | RetrievalPipeline | 串联：改写→向量检索→重排序→去重 |
| Prompt | 查询改写 Prompt 模板 | PromptRegistry 注册 |
| API | POST /search | 检索 API（返回文档不生成回答） |
| 测试 | 检索效果评估 | 标注数据集 + Recall@5/MRR |
| 测试 | 查询改写准确率 | 人工评估改写前后语义一致性 |
| 测试 | Reranker 性能 | 延迟 + 准确率对比 |

---

### Sprint 6：RAG 生成链路

| 维度 | 详情 |
|------|------|
| **时间** | 第 11-12 周 |
| **目标** | 实现 LLM 调用 + Prompt 系统 + 流式输出 + 引用校验 |
| **主题** | RAG 闭环——从"能找到"到"能回答" |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 基础设施 | LLMClient | OpenAI Compatible API + 流式 + 重试 |
| Prompt | PromptRegistry | 模板注册中心 + 版本管理 |
| Prompt | RAG System Prompt | 含引用强制要求 |
| Prompt | RAG User Prompt | Context + Question 组装 |
| RAG | PromptBuilder | 上下文截断 + 格式化 + 组装 |
| RAG | CitationValidator | 引用提取 + 完整性校验 |
| RAG | RAGPipeline | 完整 7 步管线编排 |
| API | POST /kb/{id}/chat | 流式 SSE 问答 |
| API | POST /kb/{id}/chat/sync | 非流式问答 |
| 测试 | RAG 端到端测试 | 上传文档→提问→回答+引用 |
| 测试 | 引用完整性测试 | 引用编号验证、来源追溯 |
| 测试 | 流式输出测试 | SSE 事件格式 + 连接中断处理 |

---

### Sprint 7：对话与前端问答界面

| 维度 | 详情 |
|------|------|
| **时间** | 第 13-14 周 |
| **目标** | 实现对话会话管理 + 前端问答 UI |
| **主题** | 用户可以自然地对话了 |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 数据库 | conversations 表 Migration | |
| 数据库 | messages 表 Migration | |
| ORM 模型 | Conversation / Message | |
| Repository | ConversationRepository | CRUD + 分页 |
| Service | ConversationService | 会话管理 + 消息存储 |
| API | POST /conversations | 手动创建对话 |
| API | GET /conversations | 对话列表 |
| API | GET /conversations/{id}/messages | 消息历史 |
| API | DELETE /conversations/{id} | 删除对话 |
| API | POST /messages/{id}/feedback | 消息反馈 |
| 前端 | 问答页面 | Chat UI + 流式显示 + Markdown 渲染 |
| 前端 | 引用卡片组件 | 侧边栏展示引用来源 |
| 前端 | 对话历史侧边栏 | 对话列表 + 切换 |
| 前端 | 反馈按钮 | 点赞/点踩 |
| 测试 | 对话 API 集成测试 | 创建会话→消息→查询历史 |

---

### Sprint 8：MVP 收尾与部署

| 维度 | 详情 |
|------|------|
| **时间** | 第 15-16 周 |
| **目标** | 全链路联调、性能优化、Docker 生产部署、文档完善 |
| **主题** | 🚀 MVP 正式发布 |

**交付物**：

| 类别 | 交付内容 | 说明 |
|------|---------|------|
| 联调 | 前后端全链路测试 | 所有 P0 用户故事验证通过 |
| 优化 | 数据库查询优化 | N+1 检查、慢查询优化 |
| 优化 | 检索延迟优化 | P95 < 2s |
| 优化 | 前端加载体验 | Skeleton + 懒加载 |
| 部署 | Dockerfile（多阶段构建） | API + Worker |
| 部署 | docker-compose.prod.yml | 生产环境编排 |
| 部署 | Nginx 配置 | 反向代理 + 静态资源 + 限流 |
| 部署 | 一键启动脚本 | start.sh / start.ps1 |
| 文档 | 用户使用手册 | 快速开始指南 |
| 文档 | 所有 docs/ 审校 | 一致性检查 + 更新 |
| 测试 | 性能压测 | 100 并发，P95 < 15s |
| 发布 | v1.0.0 Release | Tag + CHANGELOG + Release Notes |

---

## 4. Sprint 9-16：v1.5 / v2.0 概要规划

### v1.5 增强版（Sprint 9-12，第 17-24 周）

| Sprint | 主题 | 核心交付物 |
|--------|------|-----------|
| 9 | 混合检索 | BM25 索引（PostgreSQL tsvector + jieba）、RRF 融合、HybridRetriever 重构 |
| 10 | RBAC 权限 | 角色权限中间件、知识库级别授权、API 权限校验、前端权限控制 |
| 11 | 多轮对话 | 对话上下文融合、指代消解、对话摘要、历史消息 Token 裁剪 |
| 12 | 反馈 + 批量 | 用户反馈分析面板、批量上传（拖拽多文件）、Word 文档解析、性能调优 |

### v2.0 企业版（Sprint 13-16，第 25-32 周）

| Sprint | 主题 | 核心交付物 |
|--------|------|-----------|
| 13 | 跨知识库 | 跨知识库检索、知识库关联、统一检索入口 |
| 14 | 数据分析 | 数据看板（问答趋势/热门问题/用户活跃度）、图表可视化 |
| 15 | SSO + API | OAuth 2.0 / SAML 集成、开放 API + API Key 管理、Rate Limiting |
| 16 | 生产就绪 | K8s Helm Chart、Prometheus + Grafana、压测报告、安全审计、v2.0 Release |

---

## 5. 里程碑节点

| 里程碑 | Sprint | 时间 | 验收标准 |
|--------|--------|------|---------|
| **M1: 项目启动** | Sprint 1 | 第 2 周末 | Docker 环境就绪、CI 通过、健康检查可用 |
| **M2: 认证就绪** | Sprint 2 | 第 4 周末 | 用户可注册/登录/获取 Token、知识库 CRUD 可用 |
| **M3: 文档可处理** | Sprint 3 | 第 6 周末 | 上传 PDF/MD/TXT → 自动完成向量化索引 |
| **M4: 前端可用** | Sprint 4 | 第 8 周末 | 前端登录/知识库/文档页面可用 |
| **M5: 检索可用** | Sprint 5 | 第 10 周末 | 检索链路完整，Recall@5 ≥ 90% |
| **M6: RAG 闭环** | Sprint 6 | 第 12 周末 | 完整问答链路，流式返回，引用正常 |
| **M7: Alpha 测试** | Sprint 7 | 第 14 周末 | 前端完整可用，内部试用 |
| **🚀 M8: MVP 发布** | Sprint 8 | 第 16 周末 | Docker 一键部署，所有 P0 功能通过验收 |

---

## 6. 风险识别与应对

| # | 风险 | 概率 | 影响 | 应对策略 |
|---|------|:---:|:---:|---------|
| R1 | **LLM API 不稳定**<br/>（限流、超时、服务降级） | 中 | 🔴 高 | ① 支持多 Provider 切换（OpenAI / Claude / 通义千问）<br/>② 增加重试机制（3次指数退避）<br/>③ 降级策略：检索结果直接展示 |
| R2 | **Embedding 模型效果不达预期**<br/>（中文语义匹配差） | 中 | 🟡 中 | ① 预留模型评估脚本<br/>② 支持多模型对比（bge-large-zh / text-embedding-3）<br/>③ P0 阶段先选最优模型，P1 做 A/B 对比 |
| R3 | **检索效果差**<br/>（用户反馈答案不对） | 高 | 🟡 中 | ① Sprint 5 就开始用标注数据集评估<br/>② 留足调优时间（参数搜索 + 策略迭代）<br/>③ Hybrid Search + Rerank 提前到 P0 如果纯向量不够 |
| R4 | **文档解析兼容性差**<br/>（特殊 PDF、乱码、格式） | 中 | 🟡 中 | ① P0 只支持 PDF/MD/TXT<br/>② Word/HTML 后置到 P1<br/>③ 收集真实文档样本做测试 |
| R5 | **Qdrant 性能瓶颈**<br/>（百万级向量时检索变慢） | 低 | 🔴 高 | ① HNSW 参数可调（m, ef_construct）<br/>② Qdrant 支持分段和量化<br/>③ 预留迁移到 Milvus 的方案（ADR-001） |
| R6 | **单人开发进度风险**<br/>（预估偏差、任务阻塞） | 高 | 🟡 中 | ① 严格 MVP 边界，P1/P2 果断后移<br/>② 每个 Sprint 有明确 DoD，不镀金<br/>③ 每日 Standup（自己 review 进度） |
| R7 | **前端开发速度慢**<br/>（React 生态不熟悉） | 中 | 🟡 中 | ① 使用 TailwindCSS + shadcn/ui 组件库加速<br/>② MVP 阶段 UI 简洁优先，不追求炫酷<br/>③ 复杂图表（ECharts）后置到 v2.0 |

### 风险应对优先级

```
R6 (进度) > R1 (LLM API) > R3 (检索效果) > R2 (Embedding) > R4 (解析) > R7 (前端) > R5 (Qdrant)
```

---

> **下一步**: 阅读 [详细任务拆分 (TASKS.md)](./TASKS.md) 查看每个 Sprint 的具体 Task。
