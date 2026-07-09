"""
应用配置管理模块

使用 Pydantic Settings 统一管理所有配置项，支持：
- .env 文件加载
- 环境变量覆盖
- 类型校验
- 配置分类管理

使用示例:
    from app.core.config import get_settings
    settings = get_settings()
    print(settings.APP_NAME)
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """全局配置，按职责分为多个配置组"""
    # ===== 应用基础配置 =====
    APP_NAME: str = "企业知识库RAG"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ===== 数据库配置 =====
    DATABASE_URL: str = "postgresql+asyncpg://raguser:ragpassword@localhost:5432/ragdb"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ===== Redis 配置 =====
    REDIS_URL: str = "redis://localhost:6379/0"

    # ===== LLM 配置 =====
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 2048

    # ===== Embedding 配置 =====
    EMBEDDING_API_KEY: str | None = None  # 默认复用 LLM_API_KEY
    EMBEDDING_BASE_URL: str | None = None  # 默认复用 LLM_BASE_URL
    EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIMENSION: int = 3072
    EMBEDDING_BATCH_SIZE: int = 32

    # ===== Qdrant 向量数据库配置 =====
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "kb_chunks"
    QDRANT_VECTOR_SIZE: int = 3072

    # ===== 安全配置 =====
    JWT_SECRET_KEY: str = "dev-secret-key-change-in-production"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 小时
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # 7 天
    BCRYPT_ROUNDS: int = 12

    # ===== 文件上传配置 =====
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100

    # ===== RAG 参数配置 =====
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 50
    RERANK_TOP_K: int = 10

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """获取全局配置（单例模式）"""
    return Settings()
