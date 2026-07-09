# 架构决策记录 (Architecture Decision Records)

> **文档版本**: v1.0
> **创建日期**: 2026年7月10日
> **状态**: Living Document（随项目演进持续更新）

---

## 什么是 ADR？

**架构决策记录（ADR）** 是一份轻量级的文档，用于记录项目中的重要架构决策。每条 ADR 包含：

- **决策内容**（我们选择了什么）
- **理由**（为什么这样选择）
- **权衡**（我们牺牲了什么）
- **备选方案**（我们还考虑了什么）

---

## ADR 索引

| ADR | 决策 | 状态 | 日期 |
|-----|------|------|------|
| [ADR-001](#adr-001) | 选择 Qdrant 作为向量数据库 | ✅ Accepted | 2026-07-10 |
| [ADR-002](#adr-002) | 采用 DDD 分层架构 | ✅ Accepted | 2026-07-10 |
| [ADR-003](#adr-003) | 选择 FastAPI 作为 Web 框架 | ✅ Accepted | 2026-07-10 |
| [ADR-004](#adr-004) | 选择 PostgreSQL 作为关系数据库 | ✅ Accepted | 2026-07-10 |
| [ADR-005](#adr-005) | 检索采用 Hybrid Search + RRF 融合 | ✅ Accepted | 2026-07-10 |
| [ADR-006](#adr-006) | 分块策略使用 RecursiveCharacterTextSplitter | ✅ Accepted | 2026-07-10 |
| [ADR-007](#adr-007) | 配置管理使用 Pydantic Settings | ✅ Accepted | 2026-07-10 |
| [ADR-008](#adr-008) | 代码质量工具使用 Black + Ruff + MyPy | ✅ Accepted | 2026-07-10 |

---

## ADR-001：选择 Qdrant 作为向量数据库

### Status
✅ **Accepted**

### Context

RAG 系统需要一个向量数据库来存储文档的 Embedding 向量，并支持高效的近似最近邻（ANN）检索。

候选方案：
- **Qdrant** — Rust 编写，单二进制部署，内置 Payload 索引
- **Milvus** — Go 编写，功能完整但依赖复杂（etcd + MinIO）
- **Weaviate** — Go 编写，GraphQL 接口
- **Chroma** — Python 编写，极其轻量

### Decision

**使用 Qdrant** 作为项目的向量数据库。

### Reason

1. **部署极简**：Qdrant 在 Docker Compose 中只需要一个服务，而 Milvus Standalone 需要 etcd + MinIO + Milvus 三个服务。MVP 阶段运维简单性 > 功能完整性。

2. **性能优异**：Rust 编写，HNSW 索引，单机即可支撑百万级向量检索。

3. **Payload 索引**：Qdrant 原生支持 Payload（元数据）索引，可以高效执行 `kb_id=xxx AND document_type=pdf` 这类过滤查询，无需像 Milvus 那样使用 Scalar Index。

4. **API 友好**：提供 gRPC 和 REST 双协议，Python SDK 简洁易用。

5. **社区健康**：GitHub 20K+ Stars，Apache 2.0 许可证，更新活跃。

### Trade-off

| 牺牲 | 说明 |
|------|------|
| **分布式集群** | Milvus 的分布式集群方案更成熟。Qdrant 的集群模式相对较新。MVP 阶段单机足够，v2.0 再评估是否需要迁移。 |
| **生态规模** | Milvus 的社区生态更大（30K+ Stars），第三方集成更多。 |
| **中文分词** | Milvus 内置中文分词器，Qdrant 需在应用层处理。本项目在应用层（BM25）做分词，不依赖数据库。 |

### Alternative

| 方案 | 优点 | 未选原因 |
|------|------|---------|
| **Milvus** | 功能最完整、分布式成熟、中文分词 | 部署依赖链太重（etcd + MinIO），MVP 阶段运维负担大 |
| **Weaviate** | GraphQL 接口新颖、内置向量化模块 | Go 生态与团队 Python 技术栈不匹配，学习成本高 |
| **Chroma** | 极简、Python 原生、零配置 | 性能不足以支撑企业场景，缺少生产级特性（备份/集群） |

### Consequences

- Docker Compose 中少维护 2 个服务（etcd、MinIO）
- 需要在应用层实现 BM25 关键词索引（配合 PostgreSQL）
- 分布式部署时需重新评估（v2.0）

---

## ADR-002：采用 DDD 分层架构

### Status
✅ **Accepted**

### Context

项目需要选择一个可维护、可扩展的架构模式。在 Python FastAPI 生态中，常见做法是：

- **MVC 模式**：Model（SQLAlchemy）— View（Router）— Controller（Service），但 Router 和 Service 边界模糊
- **DDD 分层**：API → Application → Domain → Infrastructure，层次分明
- **扁平结构**：所有逻辑写在 Router 函数中（"fat router" 反模式）

### Decision

**采用 DDD（领域驱动设计）四层架构**：
- API 层（Router）：参数校验、路由转发
- Application 层（Service）：业务流程编排
- Domain 层（Entity/ValueObject）：纯业务规则
- Infrastructure 层（Repository/外部服务）：数据访问和外部调用

### Reason

1. **职责清晰**：每层有明确的职责边界，"Router 不允许有业务逻辑"是铁律，可强制执行。

2. **可测试性**：Service 层不依赖 HTTP/数据库，可以纯单元测试。Repository 和外部服务可以被 Mock。

3. **可替换性**：切换 Embedding 模型、LLM Provider、向量数据库时，只需替换 Infrastructure 层实现，业务代码不动。

4. **团队协作**：分层后每个人负责不同层，边界清晰，减少代码冲突。

5. **面试价值**：DDD 是业界公认的高级架构模式，能体现架构设计能力。

### Trade-off

| 牺牲 | 说明 |
|------|------|
| **代码量增加** | 相比于"所有逻辑写 Router 里"，DDD 分层会多出 Repository、Service 等文件。但这是有意的复杂度，换来的是可维护性。 |
| **简单 CRUD 过度工程化** | 对于"查一个用户"这种简单操作，Router → Service → Repository 三层调用显得有些重。这是我们接受的设计代价。 |

### Alternative

| 方案 | 优点 | 未选原因 |
|------|------|---------|
| **MVC（扁平）** | 开发快、代码少 | Router 会膨胀成"上帝函数"，后期难以维护。Demo 可以这样做，企业项目不行。 |
| **Clean Architecture** | 更纯粹的依赖反转 | 过于抽象，Python 生态缺少成熟的 Clean Architecture 框架支持，学习成本高。 |
| **CQRS** | 读写分离、适合复杂查询 | 当前 MVP 阶段查询场景不复杂，CQRS 带来的 Command/Query 分离收益不抵成本。v2.0 可引入。 |

### Consequences

- 所有开发者必须遵守分层铁律（见 project-context.md）
- Code Review 时重点检查是否有跨层调用
- 新增模块时需先定义 Service 接口和 Repository 接口

---

## ADR-003：选择 FastAPI 作为 Web 框架

### Status
✅ **Accepted**

### Context

Python 后端框架的选择直接影响开发效率、性能和可维护性。

候选方案：
- **FastAPI** — 异步优先、自动 OpenAPI、Pydantic 集成
- **Django Ninja** — Django 生态 + FastAPI 风格
- **Flask** — 经典微框架、生态成熟

### Decision

**使用 FastAPI** 作为 Web 框架。

### Reason

1. **原生异步**：FastAPI 基于 Starlette，原生支持 `async/await`。RAG 系统的文档处理、LLM 调用、向量检索都是 I/O 密集型操作，异步能大幅提升并发能力。

2. **自动 API 文档**：FastAPI 自动生成 OpenAPI Schema，Swagger UI 和 ReDoc 开箱即用。对于前后端分离项目，API 文档自动维护，不额外消耗精力。

3. **Pydantic 深度集成**：请求校验、响应序列化、配置管理全部基于 Pydantic，类型安全贯穿全栈。

4. **性能**：Starlette + Uvicorn 的组合在 Python Web 框架中性能第一梯队。

5. **社区与生态**：GitHub 75K+ Stars，FastAPI 用户社区庞大，中间件和扩展丰富。

### Trade-off

| 牺牲 | 说明 |
|------|------|
| **缺少 Django Admin** | Django 自带的后台管理在 FastAPI 中没有等价物。需要自己实现或使用第三方库（如 SQLAdmin）。MVP 阶段手写管理 API。 |
| **ORM 选择分散** | Django 有"唯一"的 ORM，FastAPI 生态 ORM 选择多（SQLAlchemy / Tortoise / Peewee），需要额外决策。 |
| **缺乏 Django 的"电池"** | Django 自带认证、Session、CSRF 等。FastAPI 需要自己组装，但换来的是灵活性。 |

### Alternative

| 方案 | 优点 | 未选原因 |
|------|------|---------|
| **Django Ninja** | Django 生态（Admin/ORM/Auth） + FastAPI 风格 | 仍然依赖 Django 的重量级基础，异步支持是后来加的（不够原生） |
| **Flask** | 极简、灵活、生态成熟 | 不支持原生异步（需额外扩展），无自动 API 文档，类型验证需手动 |
| **Litestar** (前 Starlite) | FastAPI 的有力竞争者，更严格的类型系统 | 社区和生态远不如 FastAPI，2024 年仍较新 |

### Consequences

- 所有 API 自动获得 Swagger 文档
- 需要自行实现认证中间件和后台管理
- 异步编程模式成为团队基本功

---

## ADR-004：选择 PostgreSQL 作为关系数据库

### Status
✅ **Accepted**

### Context

项目需要存储用户信息、知识库配置、文档元数据、对话记录等结构化数据。

候选方案：
- **PostgreSQL 16** — 功能最全的开源关系数据库
- **MySQL 8** — 最流行的开源数据库
- **MongoDB** — 文档型 NoSQL

### Decision

**使用 PostgreSQL 16** 作为关系数据库。

### Reason

1. **pgvector 扩展**：PostgreSQL 原生支持向量存储和检索（pgvector），可作为 Qdrant 的备份方案或轻量场景的替代方案。

2. **JSONB 支持**：PostgreSQL 的 JSONB 类型支持索引、查询、部分更新。文档元数据（metadata）用 JSONB 存储，既灵活又不牺牲查询能力。

3. **ACID 严格**：PostgreSQL 的 ACID 实现是所有开源数据库中最严格的。知识库管理、权限配置等需要事务保证的场景非常适合。

4. **全文搜索**：PostgreSQL 内置 `tsvector` 全文搜索，可配合中文分词（zhparser / jieba）实现 BM25 关键词检索。

5. **MySQL 的不足**：MySQL 的 JSON 支持不如 PostgreSQL（无 JSONB 索引），无原生向量扩展，ACID 在某些引擎下不完整。

### Trade-off

| 牺牲 | 说明 |
|------|------|
| **运维复杂度** | PostgreSQL 的配置调优比 MySQL 复杂。但 Docker 部署场景下影响不大。 |
| **生态工具** | MySQL 的 GUI 工具（Navicat 等）更丰富。PostgreSQL 推荐 DBeaver / pgAdmin。 |
| **水平扩展** | MySQL 的读写分离和分库分表方案更成熟。PostgreSQL 也有 Citus 等方案，但 MVP 阶段不需要。 |

### Alternative

| 方案 | 优点 | 未选原因 |
|------|------|---------|
| **MySQL 8** | 部署简单、GUI 工具多、国内流行 | 无原生向量扩展，JSON 不如 PostgreSQL JSONB 强大 |
| **MongoDB** | 灵活的 Schema-less、适合文档存储 | 本项目大量结构化关系数据（用户-知识库-文档），MongoDB 的事务和 JOIN 支持不如关系数据库 |
| **SQLite** | 零配置、嵌入式 | 不支持并发写入、无 pgvector、不适合 Web 服务场景 |

### Consequences

- 数据库迁移使用 Alembic
- 利用 pgvector 作为向量检索的备用方案
- JSONB 列用于存储灵活的 metadata

---

## ADR-005：检索采用 Hybrid Search + RRF 融合

### Status
✅ **Accepted**

### Context

RAG 系统的检索质量直接影响最终回答的准确性。需要决定检索策略。

候选方案：
- **纯向量检索（Dense Only）** — 只做向量语义检索
- **纯关键词检索（Sparse Only）** — BM25 精确匹配
- **混合检索（Hybrid）** — 向量 + 关键词融合

### Decision

**采用 Hybrid Search（向量语义 + BM25 关键词）+ RRF 融合算法**。

### Reason

1. **互补性**：向量检索擅长语义匹配（"年假"能匹配到"带薪休假"），BM25 擅长精确匹配（"ARPU-2024-001"等编号/术语）。两者结合覆盖更全。

2. **RRF 无需调参**：Reciprocal Rank Fusion 不需要像加权融合那样调权重参数。`k=60` 是业界广泛验证的经验值。

3. **中文场景验证**：大量中文 RAG 实践（BGE、RagFlow 等）证明 Hybrid + RRF 是最稳健的检索策略。

### Trade-off

| 牺牲 | 说明 |
|------|------|
| **复杂度增加** | 需要维护两套索引：Qdrant（向量）+ PostgreSQL tsvector 或内存 BM25 索引 |
| **检索延迟** | 两路检索并行执行，但增加了融合步骤。实测延迟增加 < 100ms |
| **存储成本** | BM25 索引需要额外存储分词结果 |

### Alternative

| 方案 | 优点 | 未选原因 |
|------|------|---------|
| **纯向量检索** | 实现简单、只需 Qdrant | 精确术语匹配差，中文短语/编号命中率低 |
| **纯 BM25** | 实现简单、精确匹配强 | 语义理解弱，同义词/近义词无法匹配 |
| **加权融合** | 可灵活调整 Dense/Sparse 权重 | 需要针对每个知识库调参，不可泛化 |

### Consequences

- 需要额外维护 BM25 索引（使用 PostgreSQL tsvector 或 jieba 分词 + 内存索引）
- v1.0 MVP 可用纯向量检索先行，v1.5 必须加上混合检索
- RRF 参数 k=60 固化在代码中

---

## ADR-006：分块策略使用 RecursiveCharacterTextSplitter

### Status
✅ **Accepted**

### Context

文档分块（Chunking）是 RAG 的基础环节。分块方式直接影响检索精度和上下文完整性。

候选方案：
- **固定大小分块** — 按固定 Token 数切分
- **递归字符分割** — 按分隔符优先级递归切分
- **语义分块** — 基于 Embedding 相似度切分
- **Sentence Window** — 检索句子但返回更大的窗口

### Decision

**使用 RecursiveCharacterTextSplitter**（递归字符分割）。

参数标准：
- `chunk_size`: 500 tokens（范围 500~800）
- `chunk_overlap`: 100 tokens
- 分隔符优先级：`\n## ` → `\n### ` → `\n` → `。` → `. ` → `；` → ` `

### Reason

1. **结构感知**：递归分割会优先在 Markdown 标题、段落、句子边界切分，比简单的固定 Token 数切分更尊重文档结构。

2. **chunk_size=500 的理由**：太小（<300）语义不完整，太大（>1000）噪声多。500 token 约等于 1-2 个完整段落，语义完整且检索精准。

3. **overlap=100 的理由**：20% 的重叠率确保相邻 Chunk 之间的语义连续性，避免关键信息刚好落在两个 Chunk 的边界上被截断。

4. **业界验证**：LangChain 的默认分块策略，LlamaIndex、RagFlow 等框架均采用类似策略。

### Trade-off

| 牺牲 | 说明 |
|------|------|
| **代码/表格可能被截断** | 对于 Markdown 代码块和大表格，可能在中间被截断。需要后期考虑特殊保护策略。 |
| **非标准文档格式** | 对于没有清晰段落结构的文档（如聊天记录），递归分割退化为近似固定大小分块。 |

### Alternative

| 方案 | 优点 | 未选原因 |
|------|------|---------|
| **语义分块** | 语义边界更自然 | 需要多一步 Embedding + 相似度计算，增加处理时间。MVP 阶段收益不明显。 |
| **Sentence Window** | 检索精准 + 上下文完整 | 增加检索后的二次查询，延迟增加。v1.5 可考虑。 |
| **固定大小分块** | 简单直接 | 不考虑结构边界，用户体验差。 |

### Consequences

- 分块器基于 LangChain `RecursiveCharacterTextSplitter` 实现
- chunk_size 可通过知识库配置调整（默认 500，范围 500~800）
- 分块完成后必须调用 `validate_chunks()` 检查质量

---

## ADR-007：配置管理使用 Pydantic Settings

### Status
✅ **Accepted**

### Context

项目需要管理多种配置：数据库连接、LLM API Key、Embedding 模型、安全密钥等。

### Decision

**使用 Pydantic Settings** 统一管理所有配置。

### Reason

1. **类型安全**：配置项有完整类型注解，IDE 自动补全，拼写错误在启动时就报错。
2. **多来源支持**：`.env` 文件 + 环境变量 + 默认值，开发和生产环境无缝切换。
3. **FastAPI 原生集成**：与 FastAPI 的 Depends 机制无缝配合，@lru_cache 实现单例。
4. **分类管理**：按职责分为 7 个配置类（App/DB/Redis/LLM/Embedding/Qdrant/Security），清晰不混乱。

### Consequences

- .env 文件不纳入 Git（.gitignore）
- 提供 .env.template 供新开发者参考
- 敏感配置（API Key / JWT Secret）通过环境变量注入

---

## ADR-008：代码质量工具使用 Black + Ruff + MyPy

### Status
✅ **Accepted**

### Context

需要选择 Python 代码的格式化、Lint 和类型检查工具。

### Decision

使用 **Black（格式化）+ Ruff（Lint + 导入排序）+ MyPy（类型检查）**。

### Reason

1. **Black**：业界最流行的 Python 格式化工具，零配置，"只有一种正确格式"的理念避免团队争论。
2. **Ruff**：Rust 编写的超快 Linter，替代 Flake8 + isort + pyupgrade 等十几种工具，单一工具覆盖所有 Lint 规则。
3. **MyPy**：Python 类型检查的行业标准，strict 模式确保类型安全。

### Consequences

- CI Pipeline 必须通过 Black Check + Ruff + MyPy
- pyproject.toml 中配置所有工具参数
- 推荐使用 pre-commit hook 在提交前自动检查

---

## 模板：新增 ADR

```markdown
## ADR-XXX：决策标题

### Status
🟡 Proposed / ✅ Accepted / ❌ Deprecated / 🔄 Superseded by ADR-XXX

### Context
描述决策背景和需要解决的问题。

### Decision
明确写出我们做了什么决定。

### Reason
列出为什么这样选择（1, 2, 3...）。

### Trade-off
| 牺牲 | 说明 |
|------|------|
| ... | ... |

### Alternative
| 方案 | 优点 | 未选原因 |
|------|------|---------|
| ... | ... | ... |

### Consequences
这个决定带来什么影响（好的和坏的都写）。
```

---

> **下一步**: 阅读 [API 接口文档 (API.md)](./API.md)
