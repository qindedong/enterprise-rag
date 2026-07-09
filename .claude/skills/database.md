# 数据库设计技能 (Database)

## 描述
当用户涉及数据库设计、表结构定义、SQL 优化或数据迁移时，提供专业的数据库设计指导。

## 触发条件
- 用户提到"数据库"、"建表"、"SQL"、"索引"、"迁移"
- 用户需要设计数据模型或优化查询
- 用户询问数据库选型

## 数据库设计规范

### 1. RAG 系统数据库选型

| 数据库类型 | 推荐方案 | 用途 |
|-----------|---------|------|
| 关系型数据库 | PostgreSQL + pgvector | 业务数据 + 向量存储 |
| 向量数据库 | Milvus / Qdrant | 专用向量检索 |
| 缓存 | Redis | 会话缓存、查询缓存、限流 |
| 对象存储 | MinIO / S3 | 原始文档存储 |
| 搜索引擎 | Elasticsearch | 全文检索、日志分析 |
| 图数据库 | Neo4j（可选） | 知识图谱、实体关系 |

### 2. 核心表结构设计

#### 知识库表
```sql
-- 知识库信息表
CREATE TABLE knowledge_bases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,               -- 知识库名称
    description     TEXT,                                 -- 描述
    embedding_model VARCHAR(100) NOT NULL DEFAULT 'text-embedding-3-large', -- 使用的 Embedding 模型
    chunk_size      INTEGER NOT NULL DEFAULT 512,        -- 默认分块大小
    chunk_overlap   INTEGER NOT NULL DEFAULT 64,         -- 默认重叠大小
    status          VARCHAR(20) NOT NULL DEFAULT 'active', -- active | archived | deleted
    owner_id        UUID NOT NULL,                       -- 创建者
    metadata        JSONB DEFAULT '{}',                  -- 扩展元数据
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_kb_name_owner UNIQUE (name, owner_id)
);

-- 知识库表索引
CREATE INDEX idx_kb_owner ON knowledge_bases(owner_id);
CREATE INDEX idx_kb_status ON knowledge_bases(status);
```

#### 文档表
```sql
-- 文档信息表
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    title           VARCHAR(500) NOT NULL,               -- 文档标题
    file_type       VARCHAR(20) NOT NULL,                -- pdf | docx | md | txt | html
    file_size       BIGINT,                              -- 文件大小（字节）
    file_path       VARCHAR(1000),                       -- 原始文件存储路径
    content_hash    VARCHAR(64),                         -- 内容 SHA256 哈希（去重）
    status          VARCHAR(20) NOT NULL DEFAULT 'processing', -- pending | processing | completed | failed
    chunk_count     INTEGER DEFAULT 0,                   -- 分块数量
    error_message   TEXT,                                -- 处理失败时的错误信息
    metadata        JSONB DEFAULT '{}',                  -- 扩展元数据（作者、日期等）
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_doc_hash_kb UNIQUE (kb_id, content_hash)
);

-- 文档表索引
CREATE INDEX idx_doc_kb ON documents(kb_id);
CREATE INDEX idx_doc_status ON documents(status);
CREATE INDEX idx_doc_type ON documents(file_type);
CREATE INDEX idx_doc_created ON documents(created_at DESC);
```

#### 文档分块表
```sql
-- 文档分块表
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,                    -- 分块序号
    content         TEXT NOT NULL,                       -- 分块文本内容
    token_count     INTEGER,                             -- Token 数量
    page_number     INTEGER,                             -- 所在页码（PDF文档）
    section_title   VARCHAR(500),                        -- 所属章节标题
    metadata        JSONB DEFAULT '{}',                  -- 扩展元数据
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT uq_chunk_doc_index UNIQUE (document_id, chunk_index)
);

-- 分块表索引
CREATE INDEX idx_chunk_doc ON document_chunks(document_id);
CREATE INDEX idx_chunk_kb ON document_chunks(kb_id);

-- 如果使用 pgvector
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE document_chunks ADD COLUMN embedding vector(3072);
CREATE INDEX idx_chunk_embedding ON document_chunks 
    USING ivfflat (embedding vector_cosine_ops) 
    WITH (lists = 100);
```

#### 对话记录表
```sql
-- 对话会话表
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id           UUID NOT NULL REFERENCES knowledge_bases(id),
    user_id         UUID NOT NULL,
    title           VARCHAR(500),                        -- 对话标题（自动生成）
    message_count   INTEGER DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active',        -- active | archived
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_conv_user ON conversations(user_id);
CREATE INDEX idx_conv_kb ON conversations(kb_id);

-- 消息表
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(20) NOT NULL,                -- user | assistant | system
    content         TEXT NOT NULL,                       -- 消息内容
    citations       JSONB DEFAULT '[]',                  -- 引用的文档来源
    retrieval_docs  JSONB DEFAULT '[]',                  -- 检索到的文档片段
    token_usage     JSONB DEFAULT '{}',                  -- token 消耗统计
    feedback        VARCHAR(20),                         -- positive | negative | null
    feedback_comment TEXT,                              -- 用户反馈内容
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_msg_conv ON messages(conversation_id);
CREATE INDEX idx_msg_created ON messages(created_at);
```

### 3. 向量数据库设计

#### Milvus Collection 设计
```python
from pymilvus import Collection, CollectionSchema, FieldSchema, DataType

# 定义 Schema
fields = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=36, is_primary=True),
    FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=36),
    FieldSchema(name="chunk_index", dtype=DataType.INT64),
    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=3072),
    FieldSchema(name="metadata", dtype=DataType.JSON),
]

schema = CollectionSchema(
    fields=fields,
    description="RAG 文档分块向量集合",
    enable_dynamic_field=True,
)

collection = Collection(name="rag_chunks", schema=schema)

# 创建索引
index_params = {
    "metric_type": "COSINE",
    "index_type": "HNSW",
    "params": {"M": 16, "efConstruction": 200}
}
collection.create_index(field_name="embedding", index_params=index_params)
```

### 4. 数据库操作规范

#### 命名规范
- **表名**：复数形式，snake_case，如 `knowledge_bases`、`document_chunks`
- **字段名**：snake_case，见名知意，如 `created_at`、`chunk_size`
- **索引名**：`idx_表名_字段名`，如 `idx_documents_status`
- **约束名**：`约束类型_表名_字段名`，如 `uq_doc_hash_kb`
- **主键**：统一使用 UUID 类型

#### 查询规范
```python
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

class DocumentRepository:
    """文档数据访问层"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def find_by_kb(
        self,
        kb_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[list[Document], int]:
        """分页查询知识库下的文档"""
        conditions = [Document.kb_id == kb_id]
        if status:
            conditions.append(Document.status == status)
        
        # 查询总数
        count_query = select(func.count()).where(and_(*conditions))
        total = (await self.session.execute(count_query)).scalar()
        
        # 分页查询
        query = (
            select(Document)
            .where(and_(*conditions))
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await self.session.execute(query)
        documents = result.scalars().all()
        
        return documents, total
    
    async def bulk_insert_chunks(
        self,
        chunks: list[DocumentChunk]
    ) -> list[DocumentChunk]:
        """批量插入文档分块"""
        self.session.add_all(chunks)
        await self.session.flush()  # 不提交，由上层控制事务
        return chunks
```

### 5. 数据库优化原则

#### 索引策略
- 高频查询条件字段建索引
- 外键字段必须建索引
- 复合索引遵循最左前缀原则
- 定期分析慢查询日志，针对性优化
- pgvector 的 IVF_FLAT 索引适合大数据量，HNSW 适合高精度

#### 分区策略
```sql
-- 按时间范围分区（适用于日志、消息等大量数据）
CREATE TABLE messages (
    ...
) PARTITION BY RANGE (created_at);

-- 创建月度分区
CREATE TABLE messages_2024_01 PARTITION OF messages
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

#### 连接池配置
```python
# SQLAlchemy 连接池配置
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,           # 连接池大小
    max_overflow=10,        # 最大溢出连接
    pool_recycle=3600,      # 连接回收时间（秒）
    pool_pre_ping=True,     # 连接前检查有效性
    echo=False,             # 生产环境关闭 SQL 日志
)
```
