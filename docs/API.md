# 企业级智能知识库 RAG — API 接口文档

> **文档版本**: v1.0
> **创建日期**: 2026年7月10日
> **Base URL**: `http://localhost:8000/api/v1`
> **在线文档**: Swagger UI (`/docs`) | ReDoc (`/redoc`)
> **关联文档**: [ARCHITECTURE.md](./ARCHITECTURE.md) | [DATABASE.md](./DATABASE.md)

---

## 目录

1. [通用规范](#1-通用规范)
2. [认证接口](#2-认证接口)
3. [知识库接口](#3-知识库接口)
4. [文档接口](#4-文档接口)
5. [RAG 问答接口](#5-rag-问答接口)
6. [对话接口](#6-对话接口)
7. [系统接口](#7-系统接口)
8. [错误码参考](#8-错误码参考)

---

## 1. 通用规范

### 1.1 认证方式

所有需要认证的接口（标记 🔒）需在 Header 中携带 JWT Token：

```
Authorization: Bearer <access_token>
```

Token 过期后，使用 Refresh Token 获取新的 Access Token，无需重新登录。

### 1.2 统一响应格式

```json
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": { ... }
}

// 分页响应
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [ ... ],
    "page_info": {
      "total": 100,
      "page": 1,
      "page_size": 20
    }
  }
}

// 错误响应
{
  "code": 422,
  "message": "数据校验失败",
  "detail": "不支持的文件类型",
  "data": null
}
```

### 1.3 HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 请求成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 401 | 未认证（Token 过期/无效） |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 409 | 资源冲突（重复） |
| 413 | 请求体过大 |
| 422 | 数据校验失败 |
| 429 | 请求频率超限 |
| 500 | 服务器内部错误 |
| 502 | 上游服务异常（LLM/Embedding） |
| 503 | 服务暂不可用 |

---

## 2. 认证接口

### 2.1 用户注册

```http
POST /api/v1/auth/register
Content-Type: application/json
```

**Request Body:**
```json
{
  "username": "zhangsan",
  "email": "zhangsan@example.com",
  "password": "SecureP@ss123",
  "display_name": "张三"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| username | string | ✅ | 用户名，3-50 字符，字母数字下划线 |
| email | string | ✅ | 邮箱地址，唯一 |
| password | string | ✅ | 密码，8-128 字符，至少包含大小写字母和数字 |
| display_name | string | ❌ | 显示名称，默认同 username |

**Response (201):**
```json
{
  "code": 201,
  "message": "注册成功",
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "display_name": "张三",
    "created_at": "2026-07-10T10:30:00Z"
  }
}
```

**Errors:**
| 状态码 | 说明 |
|--------|------|
| 409 | 用户名或邮箱已存在 |
| 422 | 输入校验失败 |

---

### 2.2 用户登录

```http
POST /api/v1/auth/login
Content-Type: application/json
```

**Request Body:**
```json
{
  "email": "zhangsan@example.com",
  "password": "SecureP@ss123"
}
```

**Response (200):**
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "dGhpcyBpcyBhIHJlZnJl...",
    "token_type": "bearer",
    "expires_in": 86400,
    "user": {
      "id": "550e8400-...",
      "username": "zhangsan",
      "email": "zhangsan@example.com",
      "display_name": "张三",
      "role": "user"
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| access_token | 访问令牌，24 小时有效 |
| refresh_token | 刷新令牌，7 天有效 |
| expires_in | Access Token 过期时间（秒） |

**Errors:**
| 状态码 | 说明 |
|--------|------|
| 401 | 邮箱或密码错误（统一返回此消息，防止用户枚举） |
| 429 | 密码错误次数过多，请15分钟后重试 |

---

### 2.3 刷新 Token 🔒

```http
POST /api/v1/auth/refresh
Content-Type: application/json
```

**Request Body:**
```json
{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJl..."
}
```

**Response (200):**
```json
{
  "code": 200,
  "message": "Token 刷新成功",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "bmV3IHJlZnJlc2ggdG9r...",
    "token_type": "bearer",
    "expires_in": 86400
  }
}
```

---

### 2.4 获取当前用户信息 🔒

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "550e8400-...",
    "username": "zhangsan",
    "email": "zhangsan@example.com",
    "display_name": "张三",
    "role": "user",
    "is_active": true,
    "last_login_at": "2026-07-10T10:30:00Z",
    "created_at": "2026-07-01T08:00:00Z"
  }
}
```

---

## 3. 知识库接口

### 3.1 创建知识库 🔒

```http
POST /api/v1/knowledge-bases
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "name": "员工手册",
  "description": "公司各项制度和政策文档",
  "chunk_size": 500,
  "chunk_overlap": 100,
  "embedding_model": "text-embedding-3-large"
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:---:|--------|------|
| name | string | ✅ | - | 知识库名称，1-100 字符 |
| description | string | ❌ | "" | 描述，最多 500 字符 |
| chunk_size | int | ❌ | 500 | 分块大小 (500-800) |
| chunk_overlap | int | ❌ | 100 | 重叠大小 |
| embedding_model | string | ❌ | "text-embedding-3-large" | 向量化模型 |

**Response (201):**
```json
{
  "code": 201,
  "message": "知识库创建成功",
  "data": {
    "id": "kb-abc123-...",
    "name": "员工手册",
    "description": "公司各项制度和政策文档",
    "owner_id": "550e8400-...",
    "chunk_size": 500,
    "chunk_overlap": 100,
    "embedding_model": "text-embedding-3-large",
    "status": "active",
    "document_count": 0,
    "created_at": "2026-07-10T10:30:00Z"
  }
}
```

---

### 3.2 获取知识库列表 🔒

```http
GET /api/v1/knowledge-bases?page=1&page_size=20
Authorization: Bearer <access_token>
```

**Query Parameters:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页数量（最大 100） |
| search | string | - | 按名称搜索（可选） |

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "kb-abc123-...",
        "name": "员工手册",
        "description": "公司各项制度和政策文档",
        "owner_id": "550e8400-...",
        "status": "active",
        "document_count": 12,
        "chunk_count": 345,
        "created_at": "2026-07-10T10:30:00Z"
      }
    ],
    "page_info": {
      "total": 5,
      "page": 1,
      "page_size": 20
    }
  }
}
```

---

### 3.3 获取知识库详情 🔒

```http
GET /api/v1/knowledge-bases/{kb_id}
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "kb-abc123-...",
    "name": "员工手册",
    "description": "公司各项制度和政策文档",
    "owner": {
      "id": "550e8400-...",
      "display_name": "张三"
    },
    "chunk_size": 500,
    "chunk_overlap": 100,
    "embedding_model": "text-embedding-3-large",
    "status": "active",
    "stats": {
      "document_count": 12,
      "chunk_count": 345,
      "total_questions": 1280,
      "last_week_questions": 89
    },
    "member_count": 5,
    "created_at": "2026-07-10T10:30:00Z",
    "updated_at": "2026-07-10T10:30:00Z"
  }
}
```

---

### 3.4 更新知识库 🔒

```http
PUT /api/v1/knowledge-bases/{kb_id}
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body（所有字段可选）:**
```json
{
  "name": "员工手册 v2.0",
  "description": "更新后的制度文档",
  "chunk_size": 800
}
```

**Response (200):** 同 3.3

---

### 3.5 删除知识库 🔒

```http
DELETE /api/v1/knowledge-bases/{kb_id}
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "知识库已删除",
  "data": null
}
```

> ⚠️ 删除知识库会级联删除所有文档、Chunk 和 Qdrant 向量数据。

---

### 3.6 管理知识库成员 🔒

```http
# 添加成员
POST /api/v1/knowledge-bases/{kb_id}/members
# 移除成员
DELETE /api/v1/knowledge-bases/{kb_id}/members/{user_id}
# 成员列表
GET /api/v1/knowledge-bases/{kb_id}/members
```

**添加成员 Request Body:**
```json
{
  "user_id": "550e8400-...",
  "role": "editor"
}
```

| role | 权限 |
|------|------|
| admin | 管理知识库、上传/删除文档、管理成员 |
| editor | 上传/删除文档 |
| viewer | 仅提问 |

---

## 4. 文档接口

### 4.1 上传文档 🔒

```http
POST /api/v1/knowledge-bases/{kb_id}/documents
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

**Form Data:**
| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| file | file | ✅ | 要上传的文件（PDF/MD/TXT，最大 100MB） |

**Response (202):**
```json
{
  "code": 202,
  "message": "文档已提交处理",
  "data": {
    "id": "doc-xyz789-...",
    "kb_id": "kb-abc123-...",
    "title": "员工手册 v2.0.pdf",
    "file_type": "pdf",
    "file_size": 2048576,
    "status": "pending",
    "created_at": "2026-07-10T10:35:00Z"
  }
}
```

> 📌 文档上传后立即返回 202，后台异步处理（解析→分块→向量化→索引）。
> 通过 4.2 或 4.3 接口查询处理状态。

**Errors:**
| 状态码 | 说明 |
|--------|------|
| 400 | 文件格式不支持 |
| 409 | 相同内容的文档已存在 |
| 413 | 文件大小超过 100MB |

---

### 4.2 获取文档列表 🔒

```http
GET /api/v1/knowledge-bases/{kb_id}/documents?page=1&page_size=20&status=completed&search=手册
Authorization: Bearer <access_token>
```

**Query Parameters:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| page_size | int | 20 | 每页数量 |
| status | string | - | 筛选：pending / processing / completed / failed |
| file_type | string | - | 筛选：pdf / md / txt / docx |
| search | string | - | 按标题搜索 |

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "doc-xyz789-...",
        "kb_id": "kb-abc123-...",
        "title": "员工手册 v2.0.pdf",
        "file_type": "pdf",
        "file_size": 2048576,
        "status": "completed",
        "chunk_count": 45,
        "error_message": null,
        "created_at": "2026-07-10T10:35:00Z",
        "updated_at": "2026-07-10T10:37:30Z"
      }
    ],
    "page_info": {
      "total": 12,
      "page": 1,
      "page_size": 20
    }
  }
}
```

---

### 4.3 获取文档详情 🔒

```http
GET /api/v1/documents/{doc_id}
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "doc-xyz789-...",
    "kb_id": "kb-abc123-...",
    "title": "员工手册 v2.0.pdf",
    "file_type": "pdf",
    "file_size": 2048576,
    "status": "completed",
    "chunk_count": 45,
    "error_message": null,
    "chunks": [
      {
        "chunk_index": 0,
        "content_preview": "第一章 总则\n第一条 为规范公司考勤管理...",
        "token_count": 487,
        "page_number": 1,
        "section_title": "第一章 总则"
      }
    ],
    "metadata": {
      "author": "人力资源部",
      "pages": 25
    },
    "created_at": "2026-07-10T10:35:00Z",
    "updated_at": "2026-07-10T10:37:30Z"
  }
}
```

---

### 4.4 删除文档 🔒

```http
DELETE /api/v1/documents/{doc_id}
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "文档已删除",
  "data": null
}
```

> ⚠️ 删除文档会同步删除 PG 中所有 Chunk 记录和 Qdrant 中对应向量。

---

### 4.5 重新处理文档 🔒

```http
POST /api/v1/documents/{doc_id}/reprocess
Authorization: Bearer <access_token>
```

用于处理失败的文档重新触发解析。状态重置为 `pending` 并重新入队。

---

## 5. RAG 问答接口

### 5.1 RAG 问答（流式 SSE） 🔒

```http
POST /api/v1/knowledge-bases/{kb_id}/chat
Authorization: Bearer <access_token>
Content-Type: application/json
Accept: text/event-stream
```

**Request Body:**
```json
{
  "question": "公司年假有多少天？",
  "conversation_id": null,
  "top_k": 50,
  "temperature": 0.3
}
```

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:---:|--------|------|
| question | string | ✅ | - | 用户问题，1-2000 字符 |
| conversation_id | string | ❌ | null | 对话 ID（多轮对话传入） |
| top_k | int | ❌ | 50 | 检索候选数 |
| temperature | float | ❌ | 0.3 | LLM 温度（0-1） |

**SSE 事件流:**

```
event: token
data: {"content": "根据"}

event: token
data: {"content": "公司"}

event: token
data: {"content": "考勤制度"}

...

event: token
data: {"content": "天"}

event: citation
data: {"citations":[{"index":1,"document_title":"员工手册 v2.0.pdf","page_number":12,"content_snippet":"员工入职满一年后，每年享有5天带薪年假","chunk_id":"chunk-001-...","relevance_score":0.92}]}

event: done
data: {"conversation_id":"conv-20260710-001","message_id":"msg-xxx","token_usage":{"prompt_tokens":1250,"completion_tokens":180,"total_tokens":1430},"processing_time_ms":3200}
```

**Error Events:**
```
event: error
data: {"code": 400, "message": "该知识库中暂无文档"}
```

---

### 5.2 RAG 问答（非流式） 🔒

```http
POST /api/v1/knowledge-bases/{kb_id}/chat/sync
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:** 同 5.1

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "answer": "根据公司考勤制度，员工入职满一年后，每年享有 **5天** 带薪年假 [1]。\n\n### 参考资料\n[1] 《员工手册 v2.0》第12页 - \"员工入职满一年后，每年享有5天带薪年假\"",
    "citations": [
      {
        "index": 1,
        "document_title": "员工手册 v2.0.pdf",
        "chunk_id": "chunk-001-...",
        "page_number": 12,
        "content_snippet": "员工入职满一年后，每年享有5天带薪年假",
        "relevance_score": 0.92
      }
    ],
    "conversation_id": "conv-20260710-001",
    "message_id": "msg-xxx",
    "token_usage": {
      "prompt_tokens": 1250,
      "completion_tokens": 180,
      "total_tokens": 1430
    },
    "processing_time_ms": 3200
  }
}
```

---

## 6. 对话接口

### 6.1 获取对话列表 🔒

```http
GET /api/v1/conversations?kb_id=kb-abc123&page=1&page_size=20
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "conv-20260710-001",
        "kb_id": "kb-abc123-...",
        "title": "关于年假政策的咨询",
        "message_count": 4,
        "last_message_preview": "怎么申请呢？",
        "created_at": "2026-07-10T10:40:00Z",
        "updated_at": "2026-07-10T10:42:00Z"
      }
    ],
    "page_info": { "total": 15, "page": 1, "page_size": 20 }
  }
}
```

---

### 6.2 获取对话消息历史 🔒

```http
GET /api/v1/conversations/{conv_id}/messages
Authorization: Bearer <access_token>
```

**Response (200):**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "conversation_id": "conv-20260710-001",
    "messages": [
      {
        "id": "msg-001",
        "role": "user",
        "content": "公司年假有多少天？",
        "created_at": "2026-07-10T10:40:00Z"
      },
      {
        "id": "msg-002",
        "role": "assistant",
        "content": "根据公司考勤制度，员工入职满一年后...",
        "citations": [ ... ],
        "token_usage": { ... },
        "created_at": "2026-07-10T10:40:05Z"
      }
    ]
  }
}
```

---

### 6.3 删除对话 🔒

```http
DELETE /api/v1/conversations/{conv_id}
Authorization: Bearer <access_token>
```

---

### 6.4 提交消息反馈 🔒

```http
POST /api/v1/messages/{msg_id}/feedback
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "feedback": "positive",
  "comment": "回答很准确，引用也很清晰"
}
```

| feedback | 说明 |
|----------|------|
| positive | 点赞 |
| negative | 点踩 |
| null | 取消反馈 |

---

## 7. 系统接口

### 7.1 健康检查

```http
GET /health
```

**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": true,
    "redis": true,
    "qdrant": true
  },
  "timestamp": "2026-07-10T10:30:00Z"
}
```

**Response (503) — 部分服务不可用:**
```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "checks": {
    "database": true,
    "redis": true,
    "qdrant": false
  },
  "timestamp": "2026-07-10T10:30:00Z"
}
```

---

### 7.2 服务信息

```http
GET /api/v1/info
```

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "app_name": "企业知识库RAG",
    "version": "1.0.0",
    "llm_model": "gpt-4o",
    "embedding_model": "text-embedding-3-large",
    "vector_db": "Qdrant"
  }
}
```

---

## 8. 错误码参考

### 8.1 业务错误码

| code | message | 触发场景 |
|------|---------|---------|
| 400 | 请求参数错误 | 缺少必填参数 |
| 401 | 未授权 | Token 过期/无效/缺失 |
| 403 | 无权限 | 用户不是知识库成员 |
| 404 | 资源不存在 | 知识库/文档/对话不存在 |
| 409 | 资源冲突 | 用户名/邮箱已存在、文档重复上传 |
| 413 | 文件过大 | 上传文件超过 100MB |
| 422 | 数据校验失败 | 字段格式不正确 |

### 8.2 系统错误码

| code | message | 触发场景 |
|------|---------|---------|
| 429 | 请求频率超限 | 同一用户高频请求（>30次/分钟） |
| 500 | 服务器内部错误 | 未预期的异常 |
| 502 | 上游服务异常 | LLM/Embedding API 不可用 |
| 503 | 服务暂不可用 | 数据库/Redis/Qdrant 连接失败 |

### 8.3 RAG 专用错误

| detail | 说明 |
|--------|------|
| "该知识库中暂无文档，请先上传文档" | 知识库为空时提问 |
| "根据现有资料，无法回答这个问题" | 检索无相关文档 |
| "文档解析失败，请检查文件是否完整" | PDF 损坏或解析异常 |
| "AI 服务暂不可用，请联系管理员" | LLM API Key 无效或服务异常 |

---

> **下一步**: 阅读 [数据库设计 (DATABASE.md)](./DATABASE.md) 了解表结构设计。
