# ============================================================
# 企业级知识库 RAG — 后端 API 多阶段构建
# ============================================================
# 构建命令:
#   docker build --no-cache -t rag-api:latest -f backend/Dockerfile .
# 运行命令:
#   docker run -d --env-file backend/.env -p 8000:8000 rag-api:latest
# ============================================================

# ===== 阶段 1: 安装依赖 =====
FROM python:3.13-slim AS builder

WORKDIR /install

# 安装系统编译依赖（PyMuPDF 需要 C 编译器）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 只复制依赖清单
COPY backend/pyproject.toml /tmp/pyproject.toml
COPY backend/README.md /tmp/README.md

# 安装所有 Python 依赖到 /install 目录
RUN cd /tmp && pip install --no-cache-dir --prefix=/install \
    fastapi \
    uvicorn[standard] \
    sqlalchemy[asyncio] \
    asyncpg \
    alembic \
    pydantic \
    pydantic-settings \
    "redis>=5.0.0,<6.0.0" \
    httpx \
    python-jose[cryptography] \
    bcrypt \
    sentence-transformers \
    python-multipart \
    "qdrant-client>=1.9.0,<1.11.0" \
    openai \
    tiktoken \
    pymupdf \
    langchain-text-splitters \
    jieba

# ===== 阶段 2: 运行时 =====
FROM python:3.13-slim AS runtime

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制已安装的 Python 包
COPY --from=builder /install /usr/local

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash appuser

# 创建上传目录
RUN mkdir -p /app/uploads && chown -R appuser:appuser /app

# 复制应用代码
COPY --chown=appuser:appuser backend/app/ ./app/
COPY --chown=appuser:appuser backend/migrations/ ./migrations/
COPY --chown=appuser:appuser backend/alembic.ini ./

# 切换到非 root 用户
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
