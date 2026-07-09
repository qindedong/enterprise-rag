# 部署技能 (Docker)

## 描述
当用户需要容器化部署、编写 Dockerfile、配置 Docker Compose 或优化部署流程时，提供专业的 Docker 部署指导。

## 触发条件
- 用户提到"Docker"、"容器化"、"部署"、"docker-compose"、"k8s"
- 用户需要构建镜像或配置部署环境
- 用户询问如何部署到生产环境

## Docker 部署方案

### 1. 项目 Docker 架构

```
┌─────────────────────────────────────────────────┐
│                   Docker Compose                 │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Nginx   │  │  FastAPI │  │   Worker      │  │
│  │ (反向代理) │  │ (API服务) │  │ (异步任务处理) │  │
│  │  :80     │  │  :8000   │  │               │  │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  │
│       │             │               │           │
│  ┌────┴─────────────┴───────────────┴───────┐   │
│  │              PostgreSQL + pgvector       │   │
│  │                  :5432                   │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  │
│  │  Redis   │  │  Milvus  │  │   MinIO      │  │
│  │ (缓存)   │  │ (向量库)  │  │ (对象存储)    │  │
│  │  :6379   │  │ :19530   │  │  :9000       │  │
│  └──────────┘  └──────────┘  └──────────────┘  │
└─────────────────────────────────────────────────┘
```

### 2. Dockerfile（FastAPI 服务）

```dockerfile
# ===== 构建阶段 =====
FROM python:3.12-slim AS builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ===== 运行阶段 =====
FROM python:3.12-slim AS runtime

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# 从构建阶段复制已安装的依赖
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY --chown=appuser:appuser . .

# 确保本地安装的包在 PATH 中
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 切换到非 root 用户
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 3. Docker Compose 配置

```yaml
# docker-compose.yml
version: '3.8'

services:
  # ===== API 服务 =====
  api:
    build:
      context: .
      dockerfile: Dockerfile
      target: runtime
    container_name: rag-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://raguser:${DB_PASSWORD}@postgres:5432/ragdb
      - REDIS_URL=redis://redis:6379/0
      - MILVUS_HOST=milvus-standalone
      - MILVUS_PORT=19530
      - LLM_API_KEY=${LLM_API_KEY}
      - EMBEDDING_MODEL=text-embedding-3-large
    volumes:
      - ./uploads:/app/uploads          # 上传文件持久化
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      milvus-standalone:
        condition: service_healthy
    networks:
      - rag-network
    logging:
      driver: "json-file"
      options:
        max-size: "100m"
        max-file: "3"

  # ===== 异步任务 Worker =====
  worker:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rag-worker
    restart: unless-stopped
    command: celery -A app.tasks worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://raguser:${DB_PASSWORD}@postgres:5432/ragdb
      - REDIS_URL=redis://redis:6379/0
      - LLM_API_KEY=${LLM_API_KEY}
    depends_on:
      - postgres
      - redis
    networks:
      - rag-network

  # ===== PostgreSQL + pgvector =====
  postgres:
    image: pgvector/pgvector:pg16
    container_name: rag-postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_USER=raguser
      - POSTGRES_PASSWORD=${DB_PASSWORD}
      - POSTGRES_DB=ragdb
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U raguser -d ragdb"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  # ===== Redis =====
  redis:
    image: redis:7-alpine
    container_name: rag-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  # ===== Milvus 向量数据库 =====
  etcd:
    image: quay.io/coreos/etcd:v3.5.5
    container_name: rag-etcd
    restart: unless-stopped
    environment:
      - ETCD_AUTO_COMPACTION_MODE=revision
      - ETCD_AUTO_COMPACTION_RETENTION=1000
      - ETCD_QUOTA_BACKEND_BYTES=4294967296
    volumes:
      - etcd_data:/etcd
    command: etcd -advertise-client-urls=http://127.0.0.1:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd
    networks:
      - rag-network

  minio:
    image: minio/minio:latest
    container_name: rag-minio
    restart: unless-stopped
    environment:
      - MINIO_ROOT_USER=minioadmin
      - MINIO_ROOT_PASSWORD=${MINIO_PASSWORD}
    volumes:
      - minio_data:/minio_data
    command: minio server /minio_data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 20s
      retries: 3
    networks:
      - rag-network

  milvus-standalone:
    image: milvusdb/milvus:v2.3.4
    container_name: rag-milvus
    restart: unless-stopped
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_ENDPOINTS: etcd:2379
      MINIO_ADDRESS: minio:9000
    volumes:
      - milvus_data:/var/lib/milvus
    depends_on:
      - etcd
      - minio
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      timeout: 20s
      retries: 3
    networks:
      - rag-network

  # ===== Nginx 反向代理 =====
  nginx:
    image: nginx:alpine
    container_name: rag-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    networks:
      - rag-network

# 数据卷
volumes:
  postgres_data:
  redis_data:
  etcd_data:
  minio_data:
  milvus_data:

# 网络
networks:
  rag-network:
    driver: bridge
```

### 4. Nginx 配置

```nginx
# nginx/nginx.conf
upstream api_backend {
    server api:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name rag.example.com;
    
    # 强制 HTTPS（生产环境）
    # return 301 https://$host$request_uri;
    
    # 客户端上传大小限制
    client_max_body_size 100M;
    
    # API 代理
    location /api/ {
        proxy_pass http://api_backend/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;  # RAG 生成可能较慢
        
        # 限流
        limit_req zone=api_limit burst=20 nodelay;
    }
    
    # 静态文件
    location /static/ {
        alias /app/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}

# 限流配置
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=30r/m;
```

### 5. .env 模板

```bash
# .env.template — 复制为 .env 后填写实际值

# 数据库密码
DB_PASSWORD=your_secure_password_here

# MinIO 密码
MINIO_PASSWORD=your_minio_password_here

# LLM API Key
LLM_API_KEY=sk-ant-xxxxxxxxxxxxx

# 应用配置
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# 服务端口
API_PORT=8000
NGINX_PORT=80
```

### 6. .dockerignore

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
.venv/
venv/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Git
.git/
.gitignore

# 测试
tests/
.pytest_cache/
.coverage
htmlcov/

# 环境
.env
.env.local

# 文档
docs/
*.md
!README.md

# 临时文件
*.log
tmp/
uploads/
```

### 7. 部署命令速查

```bash
# 构建并启动所有服务
docker compose up -d --build

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f api
docker compose logs -f --tail=100 worker

# 重启单个服务
docker compose restart api

# 执行数据库迁移
docker compose exec api alembic upgrade head

# 进入容器调试
docker compose exec api bash

# 停止所有服务
docker compose down

# 停止并删除数据卷（危险操作！）
docker compose down -v
```
