"""
FastAPI 应用入口

组装 FastAPI 应用：
- 注册中间件（CORS、Request ID）
- 注册异常处理器
- 注册路由
- 注册生命周期事件

启动命令:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logger import get_logger
from app.middleware.request_id import RequestIDMiddleware

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"   调试模式: {settings.DEBUG}")
    logger.info(f"   日志级别: {settings.LOG_LEVEL}")
    yield
    logger.info("应用已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## 企业级智能知识库 RAG 系统

基于检索增强生成（RAG）的企业级知识管理 AI 平台。

### 核心功能
- 📚 多知识库管理
- 📄 多格式文档解析（PDF / Markdown / TXT）
- 🔍 语义向量检索
- 🤖 AI 智能问答（流式输出）
- 📎 引用来源追溯
- 💬 多轮对话

### 技术栈
- FastAPI + SQLAlchemy + PostgreSQL
- Qdrant 向量数据库
- OpenAI Compatible API
    """,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ===== 注册中间件 =====

# CORS（开发环境宽松，生产环境收紧）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"] if not settings.DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID 全链路追踪
app.add_middleware(RequestIDMiddleware)

# ===== 注册异常处理器 =====
register_exception_handlers(app)


# ===== 路由注册 =====

@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    from app.core.database import async_engine
    from sqlalchemy import text

    checks = {
        "database": False,
        "redis": False,
        "qdrant": False,
    }

    # 检查数据库
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        logger.error(f"数据库健康检查失败: {e}")

    # 检查 Redis（v1.0 不会阻塞启动）
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.close()
        checks["redis"] = True
    except Exception:
        logger.warning("Redis 健康检查失败（非阻塞）")

    # 检查 Qdrant（v1.0 不会阻塞启动）
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=settings.QDRANT_URL)
        client.get_collections()
        client.close()
        checks["qdrant"] = True
    except Exception:
        logger.warning("Qdrant 健康检查失败（非阻塞）")

    all_healthy = checks["database"]  # MVP：数据库是唯一硬性依赖
    status_code = 200 if all_healthy else 503

    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "version": settings.APP_VERSION,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# 注册 v1 API 路由
from app.api.v1.router import api_router
app.include_router(api_router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
