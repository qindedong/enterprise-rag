# 自动生成文档技能 (Documentation)

## 描述
当用户需要自动生成项目文档、API 文档、代码注释或用户手册时，提供专业的文档生成指导。

## 触发条件
- 用户提到"生成文档"、"文档"、"API 文档"、"注释"
- 用户需要编写 README、CHANGELOG 或其他项目文档
- 用户询问如何维护项目文档

## 文档生成方案

### 1. 文档体系架构

```
docs/
├── index.md                  # 文档首页
├── getting-started/          # 快速入门
│   ├── installation.md       # 安装指南
│   ├── quickstart.md         # 5分钟快速开始
│   └── configuration.md      # 配置说明
├── user-guide/               # 用户指南
│   ├── knowledge-base.md     # 知识库管理
│   ├── document-upload.md    # 文档上传
│   ├── qa-interface.md       # 问答界面
│   └── search.md             # 搜索功能
├── developer-guide/          # 开发者指南
│   ├── architecture.md       # 系统架构
│   ├── api-reference/        # API 参考（自动生成）
│   ├── rag-pipeline.md       # RAG 管线详解
│   ├── deployment.md         # 部署指南
│   └── contributing.md       # 贡献指南
├── api-reference/            # OpenAPI 自动生成
│   └── openapi.json
└── changelog.md              # 更新日志
```

### 2. API 文档自动生成

```python
# app/main.py
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="企业知识库 RAG 系统",
    description="""
## 企业级知识库 RAG（检索增强生成）系统 API

### 核心功能
- 📚 **知识库管理**：创建、管理多个知识库
- 📄 **文档管理**：上传、解析、索引文档
- 🤖 **智能问答**：基于知识库的 RAG 问答
- 🔍 **语义搜索**：向量检索 + 关键词检索

### 技术栈
- FastAPI + SQLAlchemy + PostgreSQL
- Milvus 向量数据库
- Claude API / OpenAI API
    """,
    version="1.0.0",
    docs_url="/docs",          # Swagger UI
    redoc_url="/redoc",        # ReDoc
    openapi_url="/openapi.json",
)

# 自定义 OpenAPI Schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    
    # 添加安全认证方案
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "输入 JWT Token：Bearer <token>",
        }
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

### 3. 接口文档规范

```python
from pydantic import BaseModel, Field

class RagAskRequest(BaseModel):
    """RAG 问答请求"""
    question: str = Field(
        ...,
        description="用户问题",
        json_schema_extra={"example": "公司年假有多少天？"},
        min_length=1,
        max_length=2000,
    )
    kb_id: str = Field(
        ...,
        description="知识库 ID",
        json_schema_extra={"example": "kb-abc123"},
    )
    conversation_id: Optional[str] = Field(
        None,
        description="对话 ID（多轮对话时传入）",
        json_schema_extra={"example": "conv-xyz789"},
    )
    top_k: int = Field(
        5,
        description="检索返回的文档数量",
        ge=1,
        le=20,
    )
    temperature: float = Field(
        0.3,
        description="LLM 温度参数（0-1，越高越随机）",
        ge=0,
        le=1,
    )

class RagAskResponse(BaseModel):
    """RAG 问答响应"""
    answer: str = Field(
        ...,
        description="LLM 生成的回答（Markdown 格式）",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="引用的文档来源列表",
    )
    conversation_id: str = Field(
        ...,
        description="对话 ID（用于多轮对话）",
    )
    token_usage: TokenUsage = Field(
        ...,
        description="本次请求的 Token 消耗统计",
    )
    processing_time_ms: float = Field(
        ...,
        description="处理耗时（毫秒）",
    )
```

### 4. MkDocs 文档站点配置

```yaml
# mkdocs.yml
site_name: 企业知识库 RAG 系统文档
site_description: 企业级 RAG 知识库系统完整文档
site_author: RAG 团队
repo_url: https://github.com/your-org/rag-system
repo_name: GitHub

theme:
  name: material
  language: zh
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.expand
    - search.suggest
    - search.highlight
    - content.code.copy
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-7
        name: 切换深色模式
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/brightness-4
        name: 切换浅色模式

plugins:
  - search:
      lang: zh
  - mkdocstrings:
      handlers:
        python:
          paths: [.]
          options:
            show_source: true
            show_root_heading: true
  - awesome-pages
  - git-revision-date-localized:
      enable_creation_date: true
      type: date

markdown_extensions:
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.superfences
  - pymdownx.inlinehilite
  - pymdownx.tabbed:
      alternate_style: true
  - admonition
  - footnotes
  - toc:
      permalink: true

nav:
  - 首页: index.md
  - 快速入门:
    - 安装部署: getting-started/installation.md
    - 5分钟上手: getting-started/quickstart.md
    - 配置说明: getting-started/configuration.md
  - 用户指南:
    - 知识库管理: user-guide/knowledge-base.md
    - 文档上传: user-guide/document-upload.md
    - 智能问答: user-guide/qa-interface.md
  - 开发者指南:
    - 系统架构: developer-guide/architecture.md
    - RAG 管线: developer-guide/rag-pipeline.md
    - API 参考: api-reference/
  - 更新日志: changelog.md
```

### 5. 代码文档字符串规范

```python
"""
RAG 服务模块

本模块实现了 RAG（检索增强生成）的核心问答逻辑，
包括文档检索、上下文组装、LLM 调用和引用溯源。

核心类:
    - RAGService: RAG 问答主服务
    - RetrievalPipeline: 检索管线

使用示例:
    service = RAGService(db_session, embedding_service, llm_service)
    response = await service.query(RAGQuery(question="...", kb_id="..."))
"""

class RAGService:
    """
    RAG 问答服务

    负责完整的 RAG 问答流程：
    1. 查询改写
    2. 多路检索召回
    3. 重排序
    4. 上下文组装
    5. LLM 生成
    6. 后处理

    Attributes:
        db: 数据库会话
        embedding_service: Embedding 服务实例
        llm_service: LLM 服务实例
        retriever: 混合检索器
        reranker: 重排序器

    Examples:
        >>> service = RAGService(db, emb_service, llm_service)
        >>> query = RAGQuery(question="年假是多少天？", kb_id="kb-001")
        >>> result = await service.query(query)
        >>> print(result.answer)
    """

    async def query(
        self,
        query: RAGQuery,
        conversation_id: Optional[str] = None,
    ) -> RAGResponse:
        """
        执行 RAG 问答

        完整的问答流程：改写查询 → 检索文档 → 重排序 → LLM 生成 → 后处理

        Args:
            query: 查询请求对象，包含问题和知识库 ID
            conversation_id: 对话 ID，用于多轮对话上下文

        Returns:
            RAGResponse: 包含回答、引用来源、Token 消耗等信息的响应对象

        Raises:
            ValueError: 当问题为空或知识库不存在时
            RetrievalError: 当检索过程发生错误时
            LLMError: 当 LLM 调用失败时

        Note:
            - 检索到的文档数量由 query.top_k 控制（默认5，最大20）
            - 多轮对话时，历史消息会自动拼接在上下文中
        """
        ...
```

### 6. README 模板

```markdown
# 企业知识库 RAG 系统

基于检索增强生成（RAG）的企业级知识库问答系统。

## ✨ 核心特性

- 📚 **多知识库管理**：支持创建和管理多个独立知识库
- 📄 **多格式文档解析**：PDF、Word、Markdown、TXT、HTML
- 🔍 **混合检索**：向量语义检索 + BM25 关键词检索 + RRF 融合
- 🤖 **智能问答**：基于 Claude API 的高质量 RAG 回答
- 📎 **引用溯源**：每个回答精确标注信息来源
- 💬 **多轮对话**：支持上下文感知的连续对话
- 🚀 **高性能**：异步架构，支持高并发请求

## 🏗️ 技术栈

| 组件 | 技术选型 |
|------|---------|
| 后端框架 | FastAPI (Python 3.12) |
| 数据库 | PostgreSQL + pgvector |
| 向量数据库 | Milvus |
| 缓存 | Redis |
| 对象存储 | MinIO |
| LLM | Claude API |
| Embedding | text-embedding-3-large |
| 部署 | Docker Compose |

## 🚀 快速开始

### 环境要求
- Python 3.12+
- Docker & Docker Compose
- Claude API Key

### 安装运行

\```bash
# 1. 克隆项目
git clone https://github.com/your-org/rag-system.git
cd rag-system

# 2. 配置环境变量
cp .env.template .env
# 编辑 .env 填写 LLM_API_KEY 等必要配置

# 3. 启动服务
docker compose up -d

# 4. 访问 API 文档
open http://localhost:8000/docs
\```

## 📖 文档

完整文档请访问：[文档站点链接]

## 📝 更新日志

详见 [CHANGELOG.md](./CHANGELOG.md)

## 📄 许可证

MIT License
```

### 7. 文档生成和部署命令

```bash
# 安装文档工具
pip install mkdocs mkdocs-material mkdocstrings[python] mkdocs-awesome-pages

# 本地预览文档
mkdocs serve

# 构建文档站点
mkdocs build

# 部署到 GitHub Pages
mkdocs gh-deploy

# 从代码生成 API 文档
python scripts/generate_api_docs.py

# 导出 OpenAPI 文档
curl http://localhost:8000/openapi.json > docs/api-reference/openapi.json
```
