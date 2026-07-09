# 项目上下文与架构规范 (Project Context)

## 描述
**强制技能**。定义本项目的核心架构原则和编码铁律。任何代码生成、修改、审查都必须遵守此规范。

## 触发条件
- **始终触发**：任何代码编写、修改、重构操作
- 用户提到"项目结构"、"架构"、"DDD"、"分层"
- 生成任何 Python/FastAPI 代码时

---

## 一、核心架构原则

### 1. DDD（领域驱动设计）思想

本项目采用 DDD 分层架构，严格区分各层职责：

```
┌─────────────────────────────────────────┐
│         API 层 (Router)                  │
│  只做：参数校验、路由转发、响应返回       │
│  禁止：任何业务逻辑、数据库操作           │
├─────────────────────────────────────────┤
│         Service 层 (业务逻辑)             │
│  只做：业务流程编排、业务规则校验         │
│  禁止：直接操作数据库、处理 HTTP 请求     │
├─────────────────────────────────────────┤
│         Repository 层 (数据访问)          │
│  只做：数据库 CRUD、查询封装             │
│  禁止：业务逻辑、业务规则判断             │
├─────────────────────────────────────────┤
│         Domain 层 (领域模型)             │
│  Entity、ValueObject、DomainService     │
├─────────────────────────────────────────┤
│         Infrastructure 层 (基础设施)     │
│  数据库连接、外部服务、消息队列、缓存     │
└─────────────────────────────────────────┘
```

### 2. 分层铁律（违反即为错误）

| 规则 | 说明 |
|------|------|
| **Router 禁止业务逻辑** | Router 中只能做：参数校验 → 调用 Service → 返回 Response。绝对禁止在 Router 中直接操作数据库、调用外部 API、编写业务判断 |
| **Service 负责业务** | 所有业务逻辑必须封装在 Service 层，Service 通过 Repository 访问数据 |
| **Repository 负责数据库** | 所有数据库操作必须通过 Repository，不允许在 Service 中直接写 SQL 或 ORM 查询 |
| **禁止跨层调用** | Router → Service → Repository → DB，严格单向依赖，不可反向 |
| **禁止重复代码** | 发现重复逻辑必须抽取为公共方法；同一功能只允许有一种实现 |

```python
# ❌ 错误示例 — Router 中直接写业务逻辑
@router.post("/documents/upload")
async def upload_document(file: UploadFile, db: AsyncSession = Depends(get_db)):
    content = await file.read()
    # ❌ 业务逻辑不应该在 Router 里
    if file.content_type not in ["application/pdf", "text/markdown"]:
        raise HTTPException(400, "不支持的文件类型")
    # ❌ 数据库操作不应该在 Router 里
    doc = Document(title=file.filename, status="processing")
    db.add(doc)
    await db.commit()
    return {"id": doc.id}
```

```python
# ✅ 正确示例 — Router 只做路由转发
@router.post("/documents/upload")
async def upload_document(
    file: UploadFile,
    service: DocumentService = Depends(get_document_service)
) -> APIResponse[DocumentResponse]:
    """上传文档到知识库"""
    result = await service.upload_document(file)
    return APIResponse(data=result)
```

---

## 二、统一异常处理（强制）

### 1. 异常体系

```python
# app/core/exceptions.py

class AppException(Exception):
    """应用异常基类，所有业务异常必须继承此类"""
    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)

# --- 业务异常 ---
class NotFoundException(AppException):
    """资源不存在 (404)"""
    def __init__(self, resource: str, identifier: str):
        super().__init__(404, f"{resource}不存在", f"无法找到 {resource}: {identifier}")

class ValidationException(AppException):
    """业务校验失败 (422)"""
    def __init__(self, message: str):
        super().__init__(422, "数据校验失败", message)

class DuplicateException(AppException):
    """重复资源 (409)"""
    def __init__(self, resource: str, field: str):
        super().__init__(409, f"{resource}已存在", f"{field} 的值重复")

class UnauthorizedException(AppException):
    """未授权 (401)"""
    def __init__(self, message: str = "请先登录"):
        super().__init__(401, "未授权", message)

class ForbiddenException(AppException):
    """无权限 (403)"""
    def __init__(self, message: str = "无权限执行此操作"):
        super().__init__(403, "无权限", message)

class LLMException(AppException):
    """LLM 调用异常 (502)"""
    def __init__(self, message: str):
        super().__init__(502, "LLM 服务异常", message)

class RetrievalException(AppException):
    """检索异常 (500)"""
    def __init__(self, message: str):
        super().__init__(500, "检索服务异常", message)
```

### 2. 全局异常处理器

```python
# app/core/exception_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import AppException

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一处理应用异常"""
    return JSONResponse(
        status_code=exc.code,
        content={
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail,
            "data": None,
        }
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理（未预期的异常）"""
    logger = get_logger(__name__)
    logger.error(f"未处理的异常: {type(exc).__name__}: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": "系统繁忙，请稍后重试",
            "data": None,
        }
    )

# main.py 中注册
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)
```

---

## 三、统一日志规范（强制）

### 1. Logger 定义

```python
# app/core/logger.py
import logging
import sys
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    """获取统一的 Logger 实例"""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # 控制台输出格式
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
```

### 2. 日志使用规范

```python
# ✅ 在各模块中使用统一 Logger
from app.core.logger import get_logger

logger = get_logger(__name__)

class DocumentService:
    async def upload_document(self, file: UploadFile) -> DocumentResponse:
        logger.info(f"开始处理文档上传: {file.filename}, 大小: {file.size} 字节")
        
        try:
            result = await self._process_document(file)
            logger.info(f"文档处理完成: {result.id}, 分块数: {result.chunk_count}")
            return result
        except Exception as e:
            logger.error(f"文档处理失败: {file.filename}, 原因: {str(e)}", exc_info=True)
            raise
```

### 3. 日志级别使用规则

| 级别 | 使用场景 |
|------|---------|
| DEBUG | 开发调试信息，生产环境关闭 |
| INFO | 关键业务流程节点：请求开始/结束、文档处理状态、检索耗时 |
| WARNING | 可恢复的异常：重试成功、降级处理、配置缺失使用默认值 |
| ERROR | 需要关注的错误：处理失败、外部服务调用失败、数据不一致 |

---

## 四、统一响应格式（强制）

### 1. 响应模型

```python
# app/models/response.py
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式 — 项目中所有接口必须使用此格式"""
    code: int = Field(200, description="状态码，200 表示成功")
    message: str = Field("success", description="提示信息")
    data: Optional[T] = Field(None, description="响应数据")

class PageInfo(BaseModel):
    """分页信息"""
    total: int = Field(..., description="总记录数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页数量")

class PaginatedData(BaseModel, Generic[T]):
    """分页数据"""
    items: list[T] = Field(default_factory=list, description="数据列表")
    page_info: PageInfo = Field(..., description="分页信息")

class PaginatedResponse(APIResponse[PaginatedData[T]]):
    """分页响应格式"""
    pass
```

### 2. 响应构建规范

```python
# ✅ 所有接口返回统一格式
@router.get("/documents/{doc_id}")
async def get_document(doc_id: str) -> APIResponse[DocumentResponse]:
    result = await service.get_document(doc_id)
    return APIResponse(data=result)

@router.get("/documents")
async def list_documents(page: int = 1) -> PaginatedResponse[DocumentResponse]:
    items, total = await service.list_documents(page)
    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            page_info=PageInfo(total=total, page=page, page_size=20)
        )
    )

# ❌ 禁止直接返回 dict 或裸对象
@router.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    doc = await db.query(Document).filter(Document.id == doc_id).first()
    return {"id": str(doc.id), "title": doc.title}  # ❌ 不是统一格式
```

---

## 五、Service 与 Repository 模式（强制）

### 1. Service 层规范

```python
# app/services/document_service.py
from app.core.logger import get_logger
from app.core.exceptions import NotFoundException, ValidationException
from app.repositories.document_repository import DocumentRepository
from app.models.response import DocumentResponse

logger = get_logger(__name__)

class DocumentService:
    """文档管理业务服务
    
    职责：
    - 文档上传流程编排（解析→清洗→分块→向量化→入库）
    - 业务规则校验（文件类型、大小限制、去重）
    - 跨 Repository 的事务协调
    """
    
    def __init__(
        self,
        doc_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        embedding_service: EmbeddingService,
    ):
        self.doc_repo = doc_repo
        self.chunk_repo = chunk_repo
        self.embedding_service = embedding_service
    
    async def upload_document(self, file: UploadFile) -> DocumentResponse:
        """上传并处理文档"""
        # 1. 业务校验
        self._validate_file(file)
        
        # 2. 检查是否重复
        existing = await self.doc_repo.find_by_hash(file.content_hash)
        if existing:
            raise DuplicateException("文档", f"相同内容的文档已存在: {existing.title}")
        
        # 3. 创建文档记录（通过 Repository）
        doc = await self.doc_repo.create(
            title=file.filename,
            file_type=file.extension,
            file_size=file.size,
        )
        
        # 4. 解析和分块
        chunks = await self._parse_and_chunk(file, doc)
        
        # 5. 向量化并存储
        embeddings = await self.embedding_service.embed_chunks(chunks)
        await self.chunk_repo.bulk_insert(doc.id, chunks, embeddings)
        
        # 6. 更新文档状态
        await self.doc_repo.update_status(doc.id, "completed", chunk_count=len(chunks))
        
        logger.info(f"文档上传处理完成: {doc.id}, 分块数: {len(chunks)}")
        return DocumentResponse.from_entity(doc)
    
    def _validate_file(self, file: UploadFile) -> None:
        """文件校验"""
        ALLOWED_TYPES = ["application/pdf", "text/markdown", "text/plain",
                         "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
        MAX_SIZE = 100 * 1024 * 1024  # 100MB
        
        if file.content_type not in ALLOWED_TYPES:
            raise ValidationException(f"不支持的文件类型: {file.content_type}，仅支持 PDF、Markdown、TXT、Word 文档")
        if file.size and file.size > MAX_SIZE:
            raise ValidationException(f"文件大小超过限制 ({MAX_SIZE // 1024 // 1024}MB)")
```

### 2. Repository 层规范

```python
# app/repositories/document_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models.database import Document

class DocumentRepository:
    """文档数据访问层
    
    职责：
    - 封装所有文档相关的数据库查询
    - 不包含任何业务逻辑和业务规则判断
    - 每个方法只做一件事：数据库操作
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def find_by_id(self, doc_id: str) -> Document | None:
        """按 ID 查找文档"""
        result = await self.session.execute(
            select(Document).where(Document.id == doc_id)
        )
        return result.scalar_one_or_none()
    
    async def find_by_hash(self, kb_id: str, content_hash: str) -> Document | None:
        """按内容哈希查找（去重用）"""
        result = await self.session.execute(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.content_hash == content_hash,
                Document.status != "deleted"
            )
        )
        return result.scalar_one_or_none()
    
    async def create(self, **kwargs) -> Document:
        """创建文档记录"""
        doc = Document(**kwargs)
        self.session.add(doc)
        await self.session.flush()  # 只 flush，不 commit（由上层控制事务）
        return doc
    
    async def update_status(self, doc_id: str, status: str, **kwargs) -> None:
        """更新文档状态"""
        await self.session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status=status, **kwargs)
        )
    
    async def list_by_kb(self, kb_id: str, page: int = 1, page_size: int = 20) -> tuple[list[Document], int]:
        """分页查询知识库下的文档"""
        # 查询总数
        count_result = await self.session.execute(
            select(func.count()).where(
                Document.kb_id == kb_id,
                Document.status != "deleted"
            )
        )
        total = count_result.scalar()
        
        # 分页查询
        result = await self.session.execute(
            select(Document)
            .where(Document.kb_id == kb_id, Document.status != "deleted")
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        
        return result.scalars().all(), total
    
    async def delete(self, doc_id: str) -> None:
        """软删除文档"""
        await self.session.execute(
            update(Document)
            .where(Document.id == doc_id)
            .values(status="deleted")
        )
```

---

## 六、依赖注入规范

```python
# app/api/deps.py
from functools import lru_cache
from app.core.config import Settings
from app.repositories.document_repository import DocumentRepository
from app.services.document_service import DocumentService

@lru_cache()
def get_settings() -> Settings:
    """全局配置（单例）"""
    return Settings()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """数据库会话（请求级）"""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_document_repository(db: AsyncSession = Depends(get_db)) -> DocumentRepository:
    """文档 Repository 注入"""
    return DocumentRepository(db)

def get_document_service(
    doc_repo: DocumentRepository = Depends(get_document_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
) -> DocumentService:
    """文档 Service 注入"""
    return DocumentService(doc_repo, chunk_repo, embedding_service)
```

---

## 七、Iron Law（铁律检查清单）

在生成或修改任何代码时，**必须逐条核对**：

- [ ] Router 中是否有业务逻辑？（有 → ❌ 错误）
- [ ] Router 中是否有直接的数据库操作？（有 → ❌ 错误）
- [ ] Service 中是否有直接的 SQL/ORM 查询？（有 → ❌ 错误，应通过 Repository）
- [ ] Repository 中是否有业务判断逻辑？（有 → ❌ 错误）
- [ ] 是否存在重复代码？（有 → ❌ 错误，必须抽取）
- [ ] 异常是否使用了 AppException 体系？（否 → ❌ 错误）
- [ ] 返回格式是否使用了统一 APIResponse？（否 → ❌ 错误）
- [ ] 是否使用了 get_logger 获取 Logger？（否 → ❌ 错误）
- [ ] 依赖是否通过 Depends 注入？（否 → ❌ 错误）
