# 企业级智能知识库 RAG — 技术架构设计 (Architecture Design)

> **文档版本**: v1.0
> **创建日期**: 2026年7月10日
> **作者**: RAG 开发团队
> **状态**: Draft
> **关联文档**: [PRD.md](./PRD.md) | [ADR.md](./ADR.md) | [DATABASE.md](./DATABASE.md)

---

## 目录

1. [C4 Model 架构视图](#1-c4-model-架构视图)
2. [系统全景架构图](#2-系统全景架构图)
3. [时序图](#3-时序图)
4. [DDD 分层架构详解](#4-ddd-分层架构详解)
5. [RAG Pipeline 架构](#5-rag-pipeline-架构)
6. [配置管理](#6-配置管理)
7. [可观测性架构](#7-可观测性架构)
8. [关键技术决策](#8-关键技术决策)
9. [模块划分与职责](#9-模块划分与职责)
10. [通信协议与数据流](#10-通信协议与数据流)
11. [安全架构](#11-安全架构)
12. [部署架构](#12-部署架构)

---

## 1. C4 Model 架构视图

### 1.1 Context（系统上下文图）

```mermaid
C4Context
    title 系统上下文图 — 企业级智能知识库 RAG

    Person(user, "企业员工", "通过 Web 界面提问和使用知识库")
    Person(admin, "知识管理者", "上传和管理文档")
    Person(sysadmin, "系统管理员", "管理用户、权限和系统配置")

    System(rag_system, "企业知识库 RAG 系统", "提供文档管理、语义检索和 AI 问答服务")

    System_Ext(llm_api, "LLM API", "OpenAI Compatible API<br/>提供文本生成能力")
    System_Ext(embedding_api, "Embedding API", "提供文本向量化能力")

    Rel(user, rag_system, "提问、查看回答", "HTTPS")
    Rel(admin, rag_system, "上传文档、管理知识库", "HTTPS")
    Rel(sysadmin, rag_system, "管理用户和权限", "HTTPS")
    Rel(rag_system, llm_api, "调用 LLM 生成回答", "HTTPS")
    Rel(rag_system, embedding_api, "调用 Embedding 模型", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

### 1.2 Container（容器图）

```mermaid
C4Container
    title 容器图 — 企业级智能知识库 RAG

    Person(user, "用户", "企业员工")

    System_Boundary(rag, "企业知识库 RAG 平台") {
        Container(web_app, "Web 前端", "React + TypeScript + TailwindCSS", "提供用户交互界面")
        Container(nginx, "反向代理", "Nginx", "路由、限流、SSL 终端")
        Container(api, "API 服务", "FastAPI + Python 3.12", "业务逻辑、RAG 管线编排")
        Container(worker, "异步 Worker", "Celery / ARQ", "文档解析、分块、向量化后台任务")
        ContainerDb(pg, "关系数据库", "PostgreSQL 16 + pgvector", "用户、知识库、文档、对话数据")
        ContainerDb(qdrant, "向量数据库", "Qdrant", "文档向量存储与语义检索")
        ContainerDb(redis, "缓存", "Redis 7", "会话缓存、限流计数、任务队列")
    }

    System_Ext(llm, "LLM 服务", "OpenAI Compatible API")
    System_Ext(emb, "Embedding 服务", "OpenAI Compatible API")

    Rel(user, web_app, "访问页面", "HTTPS")
    Rel(web_app, nginx, "API 请求 + SSE", "HTTPS + WSS")
    Rel(nginx, api, "反向代理", "HTTP")
    Rel(api, pg, "读写业务数据", "asyncpg")
    Rel(api, qdrant, "向量检索", "gRPC / HTTP")
    Rel(api, redis, "缓存 + 限流", "Redis Protocol")
    Rel(api, llm, "LLM 调用", "HTTPS")
    Rel(api, emb, "Embedding 调用", "HTTPS")
    Rel(worker, pg, "更新处理状态", "asyncpg")
    Rel(worker, qdrant, "写入向量", "gRPC / HTTP")
    Rel(worker, emb, "批量向量化", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

### 1.3 Component（RAG 模块组件图）

```mermaid
C4Component
    title 组件图 — RAG 问答模块

    Container_Boundary(rag_module, "RAG 问答模块") {
        Component(query_rewriter, "QueryRewriter", "LLM-based", "将用户口语化查询改写为适合检索的查询语句")
        Component(hybrid_retriever, "HybridRetriever", "Dense + Sparse", "向量检索 + BM25 关键词检索，RRF 融合，返回 Top-50")
        Component(reranker, "Reranker", "bge-reranker-v2-m3", "Cross-Encoder 精排，50 → 10")
        Component(prompt_builder, "PromptBuilder", "Template Registry", "组装 System Prompt + Context + User Question")
        Component(llm_client, "LLMClient", "OpenAI Compatible", "流式调用 LLM，SSE 推送")
        Component(citation_validator, "CitationValidator", "", "提取引用、校验完整性")
    }

    ContainerDb(qdrant, "Qdrant", "向量存储")
    ContainerDb(pg, "PostgreSQL", "BM25 索引 / 业务数据")
    System_Ext(llm, "LLM API", "")

    Rel(query_rewriter, hybrid_retriever, "改写后的查询")
    Rel(hybrid_retriever, qdrant, "向量检索", "gRPC")
    Rel(hybrid_retriever, pg, "BM25 检索", "SQL")
    Rel(hybrid_retriever, reranker, "Top-50 候选")
    Rel(reranker, prompt_builder, "Top-10 精选")
    Rel(prompt_builder, llm_client, "完整 Prompt")
    Rel(llm_client, llm, "流式生成请求", "SSE")
    Rel(llm_client, citation_validator, "生成文本 + 引用")
```

---

## 2. 系统全景架构图

```mermaid
graph TB
    subgraph Frontend["前端层 (React SPA)"]
        direction TB
        Login["登录/注册"]
        KBMgmt["知识库管理"]
        DocMgmt["文档管理"]
        ChatUI["问答界面"]
    end

    subgraph Gateway["网关层"]
        Nginx["Nginx<br/>反向代理 | 限流 | SSL"]
    end

    subgraph API_Layer["API 层 (FastAPI)"]
        direction TB
        MW["Middleware: CORS | Auth | Logging | Request ID | Rate Limit"]
        AuthRouter["/api/v1/auth/*"]
        KBRouter["/api/v1/knowledge-bases/*"]
        DocRouter["/api/v1/documents/*"]
        RAGRouter["/api/v1/rag/*"]
        ConvRouter["/api/v1/conversations/*"]
    end

    subgraph Application_Layer["Application 层 (Service)"]
        direction TB
        AuthSvc["AuthService"]
        KBSvc["KBService"]
        DocSvc["DocumentService"]
        RAGSvc["RAGService"]
        SearchSvc["SearchService"]
    end

    subgraph Domain_Layer["Domain 层"]
        direction TB
        UserEntity["User"]
        KBEntity["KnowledgeBase"]
        DocEntity["Document"]
        ChunkEntity["Chunk"]
        ConvEntity["Conversation"]
        MsgEntity["Message"]
    end

    subgraph Infrastructure["Infrastructure 层"]
        direction TB
        UserRepo["UserRepository"]
        KBRepo["KBRepository"]
        DocRepo["DocumentRepository"]
        ChunkRepo["ChunkRepository"]
        ConvRepo["ConversationRepository"]
    end

    subgraph AI_Engine["AI 引擎层"]
        direction TB
        EmbedSvc["EmbeddingService<br/>文本向量化"]
        LLMClient["LLMClient<br/>流式生成"]
        RerankerSvc["RerankerService<br/>Cross-Encoder 精排"]
        Parser["DocumentParser<br/>PDF/MD/TXT 解析"]
        Splitter["TextSplitter<br/>智能分块"]
    end

    subgraph Data_Layer["数据层"]
        direction TB
        PG["PostgreSQL 16<br/>+ pgvector"]
        Qdrant["Qdrant<br/>向量数据库"]
        Redis["Redis 7<br/>缓存"]
    end

    Frontend --> Gateway
    Gateway --> API_Layer
    API_Layer --> Application_Layer
    Application_Layer --> Domain_Layer
    Application_Layer --> Infrastructure
    Application_Layer --> AI_Engine
    Infrastructure --> Data_Layer
    AI_Engine --> Data_Layer
```

---

## 3. 时序图

### 3.1 用户上传文档

```mermaid
sequenceDiagram
    actor U as 用户
    participant FE as React 前端
    participant API as FastAPI
    participant DocSvc as DocumentService
    participant DocRepo as DocumentRepository
    participant PG as PostgreSQL
    participant Worker as 异步 Worker
    participant Parser as DocumentParser
    participant Splitter as TextSplitter
    participant EmbSvc as EmbeddingService
    participant QD as Qdrant

    U->>FE: 选择文件并上传
    FE->>API: POST /api/v1/knowledge-bases/{kb_id}/documents
    API->>API: 校验文件类型和大小
    API->>DocSvc: upload_document(file, kb_id)
    DocSvc->>DocRepo: find_by_hash(kb_id, content_hash)
    DocRepo->>PG: SELECT WHERE content_hash = ?
    PG-->>DocRepo: 无重复
    DocRepo-->>DocSvc: None
    DocSvc->>DocRepo: create(title, file_type, status="pending")
    DocRepo->>PG: INSERT INTO documents
    PG-->>DocRepo: doc_id
    DocRepo-->>DocSvc: Document
    DocSvc-->>API: DocumentResponse (status=pending)
    API-->>FE: 200 OK { doc_id, status: "pending" }
    FE-->>U: 显示"处理中..."

    Note over DocSvc,Worker: 异步处理（通过任务队列）
    DocSvc->>Worker: 入队: process_document(doc_id)

    Worker->>PG: 更新 status="processing"
    Worker->>Parser: parse(file_path)
    Parser-->>Worker: 提取的文本内容
    Worker->>Splitter: split(content, chunk_size=500, overlap=100)
    Splitter-->>Worker: chunks[]
    Worker->>EmbSvc: embed_batch(chunks)
    EmbSvc-->>Worker: embeddings[]
    Worker->>QD: upsert(vectors + payload)
    QD-->>Worker: OK
    Worker->>PG: 更新 status="completed", chunk_count=N
    Worker->>PG: 批量插入 document_chunks 记录
    Worker-->>DocSvc: 处理完成

    Note over FE,U: 用户刷新或轮询
    U->>FE: 刷新文档列表
    FE->>API: GET /api/v1/knowledge-bases/{kb_id}/documents
    API->>PG: SELECT documents WHERE kb_id=?
    PG-->>API: [{ id, title, status: "completed", chunk_count: 15 }]
    API-->>FE: 文档列表
    FE-->>U: 显示"已完成"
```

### 3.2 RAG 问答（流式）

```mermaid
sequenceDiagram
    actor U as 用户
    participant FE as React 前端
    participant API as FastAPI
    participant RAGSvc as RAGService
    participant QR as QueryRewriter
    participant HR as HybridRetriever
    participant QD as Qdrant
    participant RR as Reranker
    participant PB as PromptBuilder
    participant LLM as LLMClient
    participant CV as CitationValidator

    U->>FE: 输入问题 "公司年假有多少天？"
    FE->>API: POST /api/v1/knowledge-bases/{kb_id}/chat (Accept: text/event-stream)
    API->>RAGSvc: execute(RAGQuery)

    Note over RAGSvc,QR: Step 1: 查询改写
    RAGSvc->>QR: rewrite("公司年假有多少天？")
    QR-->>RAGSvc: "员工年假天数政策规定"

    Note over RAGSvc,HR: Step 2: 混合检索（并行）
    par 向量检索
        RAGSvc->>HR: vector_search(query, top_k=50)
        HR->>QD: search(embedding, limit=50)
        QD-->>HR: 50 条结果
    and BM25 检索
        RAGSvc->>HR: keyword_search(query, top_k=50)
        HR-->>RAGSvc: 50 条结果
    end
    HR-->>RAGSvc: RRF 融合 → Top-50

    Note over RAGSvc,RR: Step 3: 重排序
    RAGSvc->>RR: rerank(query, candidates[50])
    RR-->>RAGSvc: Top-10

    Note over RAGSvc,PB: Step 4: Prompt 组装
    RAGSvc->>PB: build(context=Top10, question)
    PB-->>RAGSvc: System Prompt + User Prompt

    Note over RAGSvc,LLM: Step 5: LLM 流式生成
    RAGSvc->>LLM: generate_stream(prompt)
    LLM-->>API: SSE chunk 1: "根据"
    API-->>FE: data: "根据"
    FE-->>U: 显示 "根据"
    LLM-->>API: SSE chunk 2: "公司"
    API-->>FE: data: "公司"
    FE-->>U: 显示 "公司"
    Note over LLM,FE: ... 逐字推送 ...
    LLM-->>API: SSE chunk N: [DONE]
    API-->>FE: data: [DONE]

    Note over RAGSvc,CV: Step 6: 引用校验
    RAGSvc->>CV: validate(answer, context_docs)
    CV-->>RAGSvc: { is_valid: true, citations: [...] }

    RAGSvc-->>API: RAGResponse(answer, citations)
    API-->>FE: 最终响应（含 citations）
    FE-->>U: 完整回答 + 引用卡片
```

---

## 4. DDD 分层架构详解

### 4.1 分层依赖关系

```
┌──────────────────────────────────────────────────────────────┐
│                    API 层 (app/api/)                          │
│                                                               │
│  职责：参数校验、路由转发、响应封装、认证注入                   │
│  依赖：Application 层 (Service)                               │
│  铁律：❌ 禁止任何业务逻辑                                    │
│        ❌ 禁止直接数据库操作                                  │
│        ❌ 禁止直接调用外部 API                                │
├──────────────────────────────────────────────────────────────┤
│                  Application 层 (app/services/)               │
│                                                               │
│  职责：业务流程编排、业务规则校验、事务协调、权限校验          │
│  依赖：Domain 层 + Infrastructure 层 + AI 引擎层              │
│  铁律：❌ 禁止直接 SQL/ORM 查询（必须通过 Repository）       │
│        ❌ 禁止直接操作 HTTP 请求/响应对象                     │
├──────────────────────────────────────────────────────────────┤
│                    Domain 层 (app/models/domain/)              │
│                                                               │
│  职责：领域实体、值对象、领域服务、业务规则（纯 Python）       │
│  依赖：无（不依赖任何框架和外部库）                            │
│  铁律：❌ 禁止依赖 FastAPI / SQLAlchemy / 任何框架           │
├──────────────────────────────────────────────────────────────┤
│              Infrastructure 层                                │
│  ┌─────────────────────┐  ┌─────────────────────────────┐    │
│  │ app/repositories/    │  │ app/infrastructure/          │    │
│  │                     │  │                             │    │
│  │ 数据访问层           │  │ 外部服务封装                 │    │
│  │ - UserRepo          │  │ - LLMClient                 │    │
│  │ - KBRepo            │  │ - EmbeddingClient           │    │
│  │ - DocRepo           │  │ - QdrantClient              │    │
│  │ - ChunkRepo         │  │ - RedisClient               │    │
│  │                     │  │ - FileStorage               │    │
│  └─────────────────────┘  └─────────────────────────────┘    │
│                                                               │
│  职责：数据库访问、外部服务调用、缓存操作、文件存储            │
│  铁律：❌ 禁止包含业务逻辑                                   │
│        ❌ 禁止包含业务规则判断                               │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 依赖注入流向

```python
# 依赖注入链（符合 project-context.md 规范）

get_settings()           # 全局配置（单例）
    ↓
get_db()                 # 数据库会话（请求级，自动 commit/rollback）
    ↓
get_*_repository(db)     # Repository 注入
    ↓
get_*_service(repo...)   # Service 注入（依赖 Repository + AI 服务）
    ↓
Router 使用 Service       # 通过 FastAPI Depends() 注入
```

### 4.3 项目目录结构

```
backend/
├── app/
│   ├── main.py                      # FastAPI 应用入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                  # 依赖注入（get_db, get_*_service）
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py            # v1 路由汇总
│   │       ├── auth.py              # 认证接口
│   │       ├── knowledge_bases.py   # 知识库接口
│   │       ├── documents.py         # 文档接口
│   │       ├── rag.py               # RAG 问答接口
│   │       └── conversations.py     # 对话接口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings
│   │   ├── exceptions.py            # 统一异常体系
│   │   ├── exception_handlers.py    # 全局异常处理器
│   │   └── logger.py               # 统一日志
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database/                # ORM 模型（SQLAlchemy）
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # Base 声明
│   │   │   ├── user.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── document.py
│   │   │   ├── document_chunk.py
│   │   │   ├── conversation.py
│   │   │   └── message.py
│   │   ├── domain/                  # 领域模型（纯 Pydantic）
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── knowledge_base.py
│   │   │   ├── document.py
│   │   │   └── rag.py
│   │   └── request_response/        # 请求/响应 DTO
│   │       ├── __init__.py
│   │       ├── response.py          # 统一响应（APIResponse 等）
│   │       ├── auth.py
│   │       ├── knowledge_base.py
│   │       ├── document.py
│   │       └── rag.py
│   ├── services/                    # Application 层
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── kb_service.py
│   │   ├── document_service.py
│   │   ├── rag_service.py
│   │   └── search_service.py
│   ├── repositories/                # Infrastructure — 数据访问
│   │   ├── __init__.py
│   │   ├── base.py                  # 基础 Repository
│   │   ├── user_repository.py
│   │   ├── kb_repository.py
│   │   ├── document_repository.py
│   │   ├── chunk_repository.py
│   │   └── conversation_repository.py
│   ├── infrastructure/              # Infrastructure — 外部服务
│   │   ├── __init__.py
│   │   ├── llm_client.py            # LLM 统一封装
│   │   ├── embedding_client.py      # Embedding 统一封装
│   │   ├── qdrant_client.py         # Qdrant 客户端
│   │   ├── redis_client.py          # Redis 客户端
│   │   └── file_storage.py          # 文件存储
│   ├── parsers/                     # 文档解析器
│   │   ├── __init__.py
│   │   ├── base.py                  # 解析器抽象接口
│   │   ├── pdf_parser.py
│   │   ├── markdown_parser.py
│   │   ├── text_parser.py
│   │   └── registry.py             # 解析器注册中心
│   ├── rag/                         # RAG 核心管线
│   │   ├── __init__.py
│   │   ├── pipeline.py              # RAG Pipeline 编排
│   │   ├── query_rewriter.py        # 查询改写
│   │   ├── hybrid_retriever.py      # 混合检索
│   │   ├── reranker.py              # 重排序
│   │   ├── prompt_builder.py        # Prompt 构建
│   │   └── citation_validator.py    # 引用校验
│   ├── prompts/                     # Prompt 模板
│   │   ├── __init__.py
│   │   ├── registry.py              # 模板注册中心
│   │   ├── rag_prompts.py           # RAG 相关模板
│   │   └── system_prompts.py        # System Prompt 模板
│   ├── middleware/                   # 中间件
│   │   ├── __init__.py
│   │   ├── request_id.py            # Request ID 注入
│   │   ├── logging.py               # 请求日志
│   │   └── rate_limit.py            # 限流
│   └── utils/                       # 工具函数
│       ├── __init__.py
│       ├── text_splitter.py         # 文档分块器
│       ├── token_counter.py         # Token 计数
│       └── security.py              # 密码哈希、JWT
├── migrations/                      # Alembic 迁移
│   ├── env.py
│   ├── versions/
│   └── alembic.ini
├── tests/
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
└── .env.template
```

---

## 5. RAG Pipeline 架构

### 5.1 完整管线流程

```mermaid
flowchart LR
    subgraph Input["输入"]
        Q["用户查询"]
    end

    subgraph Step1["Step 1: 查询改写"]
        QR["QueryRewriter<br/>LLM-based"]
    end

    subgraph Step2["Step 2: 混合检索"]
        direction TB
        VS["Vector Search<br/>Qdrant HNSW<br/>Top-50"]
        KW["Keyword Search<br/>BM25<br/>Top-50"]
        RRF["RRF 融合<br/>k=60"]
        VS --> RRF
        KW --> RRF
    end

    subgraph Step3["Step 3: 重排序"]
        RR["Cross-Encoder<br/>bge-reranker-v2-m3<br/>50 → 10"]
    end

    subgraph Step4["Step 4: 多样性过滤"]
        DF["MMR / 相似度去重<br/>threshold=0.95"]
    end

    subgraph Step5["Step 5: 上下文组装"]
        CA["PromptBuilder<br/>Context + System Prompt + Question"]
    end

    subgraph Step6["Step 6: LLM 生成"]
        LLM["LLMClient<br/>OpenAI Compatible<br/>SSE 流式"]
    end

    subgraph Step7["Step 7: 引用校验"]
        CV["CitationValidator<br/>完整性校验"]
    end

    subgraph Output["输出"]
        ANS["回答 + 引用来源"]
    end

    Q --> QR
    QR --> Step2
    RRF --> RR
    RR --> DF
    DF --> CA
    CA --> LLM
    LLM --> CV
    CV --> ANS
```

### 5.2 硬性参数标准

| 阶段 | 参数 | 硬性值 | 说明 |
|------|------|--------|------|
| 文档分块 | chunk_size | 500 tokens（范围 500~800） | RecursiveCharacterTextSplitter |
| 文档分块 | chunk_overlap | 100 tokens | 固定 |
| 混合检索 | 向量召回数 | 50 | 两路各 50 |
| 混合检索 | 融合算法 | RRF (k=60) | Reciprocal Rank Fusion |
| 混合检索 | 候选输出数 | 50 | 融合后取 Top-50 |
| 重排序 | 输入 | 50 条候选 | 来自混合检索 |
| 重排序 | 输出 | 10 条 | Cross-Encoder 精排 |
| 多样性过滤 | 相似度阈值 | 0.95 | 余弦相似度 |
| 上下文组装 | 最大文档数 | 10 | 传给 LLM 的文档数 |
| 引用校验 | 引用编号 | 必须存在 | 每个 [N] 必须能对应到文档 |

---

## 6. 配置管理

### 6.1 配置层次结构

```
┌─────────────────────────────────────┐
│            .env 文件                 │
│  DATABASE_URL=...                   │
│  LLM_API_KEY=...                    │
│  QDRANT_URL=...                     │
└──────────────┬──────────────────────┘
               │ 读取
┌──────────────▼──────────────────────┐
│      Pydantic Settings              │
│      app/core/config.py             │
│                                      │
│  ┌─────────────────────────────┐    │
│  │ AppConfig                   │    │
│  │ - APP_NAME                  │    │
│  │ - DEBUG                     │    │
│  │ - LOG_LEVEL                 │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ DBConfig                    │    │
│  │ - DATABASE_URL              │    │
│  │ - DB_POOL_SIZE              │    │
│  │ - DB_ECHO                   │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ RedisConfig                 │    │
│  │ - REDIS_URL                 │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ LLMConfig                   │    │
│  │ - LLM_API_KEY               │    │
│  │ - LLM_BASE_URL              │    │
│  │ - LLM_MODEL                 │    │
│  │ - LLM_TEMPERATURE           │    │
│  │ - LLM_MAX_TOKENS            │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ EmbedConfig                 │    │
│  │ - EMBEDDING_MODEL           │    │
│  │ - EMBEDDING_DIMENSION       │    │
│  │ - EMBEDDING_BATCH_SIZE      │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ QdrantConfig                │    │
│  │ - QDRANT_URL                │    │
│  │ - QDRANT_COLLECTION         │    │
│  │ - QDRANT_VECTOR_SIZE        │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ SecurityConfig              │    │
│  │ - JWT_SECRET_KEY            │    │
│  │ - JWT_ACCESS_TOKEN_EXPIRE   │    │
│  │ - JWT_REFRESH_TOKEN_EXPIRE  │    │
│  │ - BCRYPT_ROUNDS             │    │
│  └─────────────────────────────┘    │
└──────────────┬──────────────────────┘
               │ Depends()
┌──────────────▼──────────────────────┐
│     Dependency Injection            │
│     app/api/deps.py                  │
│                                      │
│  get_settings() → Settings (单例)    │
│  get_db() → AsyncSession (请求级)   │
│  get_*_service() → 注入到 Router   │
└─────────────────────────────────────┘
```

### 6.2 配置实现

```python
# app/core/config.py
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # 应用
    APP_NAME: str = "企业知识库RAG"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # 数据库
    DATABASE_URL: str
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM
    LLM_API_KEY: str
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048

    # Embedding
    EMBEDDING_API_KEY: str | None = None  # 默认复用 LLM_API_KEY
    EMBEDDING_BASE_URL: str | None = None
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 3072
    EMBEDDING_BATCH_SIZE: int = 32

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "kb_chunks"
    QDRANT_VECTOR_SIZE: int = 3072

    # 安全
    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24h
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12

    # 文件
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    # 分块参数（可配置但有默认值）
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 50
    RERANK_TOP_K: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

---

## 7. 可观测性架构

### 7.1 三大支柱

```
┌─────────────────────────────────────────────────────────┐
│                    可观测性体系                           │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Logging    │  │   Tracing    │  │   Metrics    │  │
│  │   日志        │  │   链路追踪    │  │   指标监控    │  │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤  │
│  │ 结构化 JSON  │  │ Request ID   │  │ 请求计数     │  │
│  │ 统一 get_    │  │ 全链路传递   │  │ 延迟分布     │  │
│  │ logger()     │  │ Middleware   │  │ 错误率       │  │
│  │ 级别控制     │  │ → Service    │  │ LLM Token    │  │
│  │              │  │ → Repository │  │ Qdrant QPS   │  │
│  │              │  │ → LLM Call   │  │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         ▼                 ▼                 ▼           │
│  ┌──────────────────────────────────────────────────┐  │
│  │              未来演进                               │  │
│  │  OpenTelemetry → Prometheus → Grafana            │  │
│  │  ELK / Loki 日志聚合                               │  │
│  │  Jaeger / Tempo 分布式追踪                          │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 7.2 Request ID 全链路追踪

```python
# Middleware 层自动注入
# app/middleware/request_id.py

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # 注入到上下文变量，后续 Service/Repository/LLM Call 均可用
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

### 7.3 健康检查

```python
# GET /health
@router.get("/health")
async def health_check():
    checks = {
        "database": await check_db(),
        "redis": await check_redis(),
        "qdrant": await check_qdrant(),
    }
    all_healthy = all(checks.values())
    status_code = 200 if all_healthy else 503
    return JSONResponse(
        content={
            "status": "healthy" if all_healthy else "unhealthy",
            "version": settings.APP_VERSION,
            "checks": checks,
        },
        status_code=status_code,
    )
```

---

## 8. 关键技术决策

> 详细决策记录见 [ADR.md](./ADR.md)，此处列出关键决策概要。

| # | 决策点 | 选择 | 核心理由 |
|---|--------|------|---------|
| 1 | 向量数据库 | **Qdrant** | 单二进制部署极简、Rust 高性能、内置 Payload 索引 |
| 2 | 关系数据库 | **PostgreSQL 16** | pgvector 扩展、JSONB 支持、ACID 严格 |
| 3 | 后端框架 | **FastAPI** | 原生异步、自动 OpenAPI、Pydantic 集成 |
| 4 | ORM | **SQLAlchemy 2.x** | 异步原生支持、成熟生态、类型安全 |
| 5 | 架构模式 | **DDD 分层** | 高内聚低耦合、每层可独立测试和替换 |
| 6 | 检索策略 | **Hybrid + RRF** | 语义 + 关键词互补，RRF 无需调参 |
| 7 | 重排序 | **bge-reranker-v2-m3** | 本地运行零成本、中文效果好、M3 多语言 |
| 8 | 配置管理 | **Pydantic Settings** | 类型安全、环境变量/.env 双支持、FastAPI 原生集成 |
| 9 | 代码质量 | **Black + Ruff + MyPy** | 业界标准、CI 友好、零配置分歧 |
| 10 | 部署方案 | **Docker Compose** | MVP 阶段最简单、资源需求低、一键启动 |

---

## 9. 模块划分与职责

| 模块 | 目录 | 核心职责 | 对外接口 |
|------|------|---------|---------|
| **认证模块** | `app/services/auth_service.py` | 用户注册/登录/JWT Token 管理/权限校验 | `AuthService.register()` / `login()` / `refresh_token()` |
| **知识库模块** | `app/services/kb_service.py` | 知识库 CRUD、成员管理、统计 | `KBService.create()` / `list()` / `add_member()` |
| **文档模块** | `app/services/document_service.py` | 文档上传编排、状态管理、删除 | `DocumentService.upload()` / `get_status()` / `delete()` |
| **解析模块** | `app/parsers/` | 多格式文档解析（PDF/MD/TXT/DOCX） | `BaseParser.parse()` → `str` |
| **分块模块** | `app/utils/text_splitter.py` | 智能文本分块 | `TextSplitter.split(text)` → `list[str]` |
| **Embedding 模块** | `app/infrastructure/embedding_client.py` | 文本向量化封装（支持多模型） | `EmbeddingClient.embed()` / `embed_batch()` |
| **向量存储模块** | `app/infrastructure/qdrant_client.py` | Qdrant 向量读写、检索 | `QdrantClient.search()` / `upsert()` / `delete()` |
| **检索模块** | `app/rag/hybrid_retriever.py` | 混合检索（向量+BM25+RRF） | `HybridRetriever.retrieve(query)` → `list[Document]` |
| **重排序模块** | `app/rag/reranker.py` | Cross-Encoder 精排 | `Reranker.rerank(query, docs)` → `list[Document]` |
| **Prompt 模块** | `app/prompts/` | Prompt 模板注册与渲染 | `PromptRegistry.render(name, **vars)` → `str` |
| **LLM 模块** | `app/infrastructure/llm_client.py` | LLM 调用封装（流式+非流式） | `LLMClient.generate()` / `generate_stream()` |
| **引用模块** | `app/rag/citation_validator.py` | 引用提取与完整性校验 | `CitationValidator.validate(answer, docs)` |
| **RAG 编排** | `app/rag/pipeline.py` | 完整 RAG Pipeline 编排 | `RAGPipeline.execute(query)` → `RAGResponse` |

---

## 10. 通信协议与数据流

### 10.1 协议矩阵

| 通信路径 | 协议 | 说明 |
|---------|------|------|
| 前端 ↔ Nginx | HTTPS | 生产环境强制 TLS |
| Nginx ↔ FastAPI | HTTP/1.1 | 内网通信 |
| FastAPI → PostgreSQL | asyncpg (PostgreSQL Wire Protocol) | 异步连接池 |
| FastAPI → Qdrant | gRPC（推荐）或 HTTP REST | 向量检索与写入 |
| FastAPI → Redis | Redis RESP | 缓存 + 限流 |
| FastAPI → LLM API | HTTPS | OpenAI Compatible API |
| FastAPI → Embedding API | HTTPS | OpenAI Compatible API |
| 前端 ↔ FastAPI (SSE) | HTTPS + SSE | 流式回答推送 |

### 10.2 流式回答数据流（SSE）

```
POST /api/v1/rag/ask
Accept: text/event-stream

← Server-Sent Events →
event: token
data: {"content": "根据"}

event: token
data: {"content": "公司"}

event: token
data: {"content": "考勤"}

...

event: citation
data: {"citations": [{"index": 1, "title": "员工手册", ...}]}

event: done
data: {"conversation_id": "conv-xxx", "token_usage": {...}}
```

---

## 11. 安全架构

### 11.1 纵深防御

```
┌──────────────────────────────────────────────┐
│              安全防护层次                       │
│                                               │
│  第 1 层：网络层                               │
│  ├── Nginx 反向代理                            │
│  ├── HTTPS 强制（TLS 1.3）                    │
│  ├── Rate Limiting（30 req/min/IP）           │
│  └── Request Size Limit（100MB）              │
│                                               │
│  第 2 层：认证层                               │
│  ├── JWT Access Token（24h）+ Refresh（7d）   │
│  ├── Password bcrypt（cost=12）               │
│  └── Token 黑名单（Redis）                    │
│                                               │
│  第 3 层：授权层                               │
│  ├── RBAC 角色权限（Viewer/Admin/SuperAdmin）  │
│  ├── 知识库级别权限隔离                         │
│  └── Repository 层强制过滤（user_id/kb_id）    │
│                                               │
│  第 4 层：应用层                               │
│  ├── 参数化查询（SQLAlchemy）                  │
│  ├── 输入校验（Pydantic）                      │
│  ├── 输出编码（XSS 防护）                      │
│  └── CSP / CORS Headers                       │
│                                               │
│  第 5 层：数据层                               │
│  ├── API Key AES-256 加密存储                  │
│  ├── 日志脱敏（密码/Token/API Key）            │
│  └── 数据库密码通过 .env（不纳入 Git）          │
└──────────────────────────────────────────────┘
```

### 11.2 认证流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as FastAPI
    participant AuthSvc as AuthService
    participant PG as PostgreSQL
    participant Redis as Redis

    Note over U,Redis: 登录
    U->>API: POST /auth/login { email, password }
    API->>AuthSvc: login(email, password)
    AuthSvc->>PG: SELECT user WHERE email=?
    PG-->>AuthSvc: user
    AuthSvc->>AuthSvc: bcrypt.verify(password, hash)
    AuthSvc->>AuthSvc: 生成 access_token + refresh_token
    AuthSvc->>Redis: 缓存 refresh_token
    AuthSvc-->>API: tokens
    API-->>U: { access_token, refresh_token }

    Note over U,Redis: API 请求
    U->>API: GET /kb { Authorization: Bearer access_token }
    API->>API: Middleware 解析 JWT → user_id
    API->>API: Depends(get_current_user) → User
    Note over API: 后续通过 Repository 强制过滤 kb_id + user_id
```

---

## 12. 部署架构

### 12.1 Docker Compose 拓扑

```mermaid
graph TB
    subgraph DockerHost["Docker Host"]
        subgraph Nginx["Nginx :80/:443"]
        end

        subgraph AppServers["API 服务 (可多副本)"]
            API1["api-1 :8000"]
            API2["api-2 :8000"]
        end

        subgraph Workers["Worker (可多副本)"]
            W1["worker-1"]
            W2["worker-2"]
        end

        subgraph Data["数据服务"]
            PG["PostgreSQL 16<br/>:5432"]
            QD["Qdrant<br/>:6333/:6334"]
            Redis["Redis 7<br/>:6379"]
        end
    end

    Nginx --> API1
    Nginx --> API2
    API1 --> PG
    API2 --> PG
    API1 --> QD
    API2 --> QD
    API1 --> Redis
    API2 --> Redis
    Workers --> PG
    Workers --> QD
    Workers --> Redis
```

### 12.2 服务清单

| 服务 | 镜像 | 端口 | 副本 | 资源限制 |
|------|------|------|------|---------|
| nginx | nginx:alpine | 80, 443 | 1 | 256MB |
| api | 自构建 | 8000 | 2 | 1GB / 2CPU |
| worker | 自构建 | — | 2 | 2GB / 2CPU |
| postgres | postgres:16 | 5432 | 1 | 2GB / 2CPU |
| qdrant | qdrant/qdrant | 6333, 6334 | 1 | 2GB / 2CPU |
| redis | redis:7-alpine | 6379 | 1 | 512MB |

---

> **下一步**: 阅读 [架构决策记录 (ADR.md)](./ADR.md) 了解每个技术决策的详细理由和权衡。
