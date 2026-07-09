# FastAPI 后端规范技能 (Backend)

## 描述
当用户编写或修改 FastAPI 后端代码时，使用此技能确保代码符合项目规范和最佳实践。

## 触发条件
- 用户编写或修改 FastAPI 路由、服务、模型代码
- 用户提到"API"、"接口"、"后端"、"FastAPI"
- 用户需要设计 RESTful API

## FastAPI 项目规范

### 1. 项目结构
```
backend/
├── api/
│   ├── v1/
│   │   ├── endpoints/
│   │   │   ├── documents.py    # 文档管理接口
│   │   │   ├── rag.py          # RAG 问答接口
│   │   │   ├── knowledge_base.py # 知识库管理
│   │   │   └── search.py       # 搜索接口
│   │   └── router.py           # v1 路由汇总
│   └── deps.py                 # 依赖注入
├── core/
│   ├── config.py               # 配置管理（Pydantic Settings）
│   ├── security.py             # 认证授权
│   └── exceptions.py           # 全局异常处理
├── models/
│   ├── domain/                 # 领域模型（Pydantic）
│   ├── database/               # 数据库模型（SQLAlchemy）
│   └── request_response/       # 请求/响应模型
├── services/                   # 业务逻辑层
├── repositories/               # 数据访问层
├── middleware/                  # 中间件
├── utils/                      # 工具函数
└── main.py                     # 应用入口
```

### 2. 路由定义规范
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

router = APIRouter(prefix="/documents", tags=["文档管理"])

@router.post(
    "/upload",
    response_model=DocumentResponse,
    summary="上传文档",
    description="上传文档到指定知识库，支持 PDF、Word、Markdown 等格式"
)
async def upload_document(
    file: UploadFile,
    kb_id: str = Query(..., description="知识库ID"),
    chunk_size: Optional[int] = Query(512, description="分块大小"),
    service: DocumentService = Depends(get_document_service)
) -> DocumentResponse:
    """
    上传文档并进行解析、分块、向量化处理。
    
    - **file**: 要上传的文件
    - **kb_id**: 目标知识库ID
    - **chunk_size**: 文档分块大小（默认512）
    """
    ...
```

### 3. 响应模型规范
```python
from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """统一响应格式"""
    code: int = Field(200, description="状态码")
    message: str = Field("success", description="提示信息")
    data: Optional[T] = Field(None, description="响应数据")

class PaginatedResponse(APIResponse[T]):
    """分页响应格式"""
    total: int = Field(..., description="总记录数")
    page: int = Field(1, description="当前页码")
    page_size: int = Field(20, description="每页数量")
```

### 4. 异常处理规范
```python
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

class AppException(Exception):
    """应用自定义异常基类"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

class DocumentNotFoundException(AppException):
    def __init__(self, doc_id: str):
        super().__init__(404, f"文档 {doc_id} 不存在")

# 全局异常处理器
@app.exception_handler(AppException)
async def app_exception_handler(request, exc: AppException):
    return JSONResponse(
        status_code=exc.code,
        content={"code": exc.code, "message": exc.message, "data": None}
    )
```

### 5. 依赖注入规范
```python
from functools import lru_cache

@lru_cache()
def get_settings() -> Settings:
    return Settings()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

def get_document_service(
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings)
) -> DocumentService:
    return DocumentService(db, settings)
```

### 6. 中间件规范
- **请求日志中间件**：记录每个请求的方法、路径、耗时、状态码
- **CORS 中间件**：配置允许的源、方法、头部
- **限流中间件**：基于 IP 或用户维度的请求频率限制
- **认证中间件**：JWT Token 验证

### 7. 配置管理
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # 应用配置
    APP_NAME: str = "企业知识库RAG"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 数据库配置
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    
    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # LLM 配置
    LLM_API_KEY: str
    LLM_MODEL: str = "claude-opus-4-8"
    LLM_BASE_URL: str = "https://api.anthropic.com"
    
    # Embedding 配置
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 3072
    
    class Config:
        env_file = ".env"
```

### 8. 代码质量要求
- 所有公共函数必须有类型注解
- 所有 API 端点必须有 `summary` 和 `description`
- 关键业务逻辑必须有中文注释
- 使用 `async/await` 处理 I/O 密集型操作
