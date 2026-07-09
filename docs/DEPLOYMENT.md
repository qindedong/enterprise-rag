# 企业级智能知识库 RAG — 部署文档

> **文档版本**: v1.0
> **创建日期**: 2026年7月10日

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速部署（5分钟）](#2-快速部署5分钟)
3. [配置说明](#3-配置说明)
4. [Docker Compose 编排详解](#4-docker-compose-编排详解)
5. [数据持久化](#5-数据持久化)
6. [健康检查与监控](#6-健康检查与监控)
7. [日志管理](#7-日志管理)
8. [备份与恢复](#8-备份与恢复)
9. [升级策略](#9-升级策略)
10. [常用运维命令速查](#10-常用运维命令速查)

---

## 1. 环境要求

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|:---:|:---:|------|
| Docker | 24.0+ | 26.0+ | 容器运行时 |
| Docker Compose | v2.20+ | v2.27+ | 容器编排 |
| Python | 3.12+ | 3.12 | 仅本地开发需要 |
| 内存 | 8 GB | 16 GB | 含所有服务 + Reranker 模型 |
| 磁盘 | 20 GB | 50 GB+ | 含向量数据、文件存储 |

---

## 2. 快速部署（5分钟）

### 2.1 一键部署

```bash
# 1. 克隆项目
git clone <your-repo-url> && cd enterprise-rag

# 2. 配置环境变量
cp .env.template .env
# 编辑 .env，至少填写：
#   - LLM_API_KEY（OpenAI Compatible API Key）
#   - JWT_SECRET_KEY（随机字符串）
#   - DB_PASSWORD（数据库密码）

# 3. 启动所有服务
docker compose up -d

# 4. 等待服务就绪（约 30 秒）
docker compose ps  # 确认所有服务状态为 healthy

# 5. 执行数据库迁移
docker compose exec api alembic upgrade head

# 6. 访问应用
# API 文档: http://localhost:8000/docs
# 健康检查: http://localhost:8000/health
```

### 2.2 验证部署

```bash
# 检查所有服务
docker compose ps

# 预期输出：
# NAME              STATUS
# rag-nginx         Up (healthy)
# rag-api           Up (healthy)
# rag-worker        Up (healthy)
# rag-postgres      Up (healthy)
# rag-qdrant        Up (healthy)
# rag-redis         Up (healthy)

# 检查健康状态
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0","checks":{"database":true,"redis":true,"qdrant":true}}
```

---

## 3. 配置说明

### 3.1 必填环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_API_KEY` | LLM API 密钥 | `sk-xxxx` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | `openssl rand -hex 32` 生成 |
| `DB_PASSWORD` | PostgreSQL 密码 | `your_secure_password` |
| `DATABASE_URL` | 数据库连接字符串 | `postgresql+asyncpg://raguser:password@postgres:5432/ragdb` |

### 3.2 可选配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM API 地址 |
| `LLM_MODEL` | `gpt-4o` | 使用的模型 |
| `EMBEDDING_MODEL` | `text-embedding-3-large` | Embedding 模型 |
| `QDRANT_URL` | `http://qdrant:6333` | Qdrant 地址 |
| `LOG_LEVEL` | `INFO` | 日志级别（DEBUG/INFO/WARNING/ERROR） |
| `MAX_FILE_SIZE_MB` | `100` | 上传文件大小上限 |

---

## 4. Docker Compose 编排详解

```yaml
services:
  nginx:       # 反向代理，端口 80/443
  api:         # FastAPI 服务，端口 8000（可多副本）
  worker:      # 异步任务处理（文档解析/分块/向量化）
  postgres:    # PostgreSQL 16 + pgvector
  qdrant:      # Qdrant 向量数据库
  redis:       # Redis 7（缓存+限流+任务队列）
```

### 4.1 扩容操作

```bash
# API 服务扩容至 3 副本
docker compose up -d --scale api=3

# Worker 扩容至 2 副本
docker compose up -d --scale worker=2
```

---

## 5. 数据持久化

| 数据 | Volume | 说明 |
|------|--------|------|
| PostgreSQL | `postgres_data` | 用户、知识库、文档、对话 |
| Qdrant | `qdrant_data` | 向量数据 |
| Redis | `redis_data` | AOF + RDB |
| 上传文件 | `./uploads` | 原始文档文件（绑定挂载） |

---

## 6. 健康检查与监控

```bash
# 查看服务健康状态
docker compose ps

# 查看 API 健康检查
curl http://localhost:8000/health

# 查看服务日志
docker compose logs -f api
docker compose logs -f --tail=100 worker
```

---

## 7. 日志管理

```yaml
# docker-compose.yml 中的日志配置
logging:
  driver: "json-file"
  options:
    max-size: "100m"   # 单个日志文件最大 100MB
    max-file: "3"      # 最多保留 3 个文件
```

```bash
# 查看日志
docker compose logs -f api                    # 实时跟踪
docker compose logs --tail=50 api             # 最近 50 行
docker compose logs --since=1h api            # 最近 1 小时
```

---

## 8. 备份与恢复

### 8.1 快速备份

```bash
# PostgreSQL 备份
docker compose exec postgres pg_dump -U raguser ragdb \
  --format=custom --file=/tmp/backup_$(date +%Y%m%d).dump
docker compose cp postgres:/tmp/backup_20260710.dump ./backups/

# Qdrant 快照
curl -X POST http://localhost:6333/collections/kb_chunks/snapshots
```

### 8.2 恢复

```bash
# PostgreSQL 恢复
docker compose cp ./backups/backup_20260710.dump postgres:/tmp/
docker compose exec postgres pg_restore -U raguser -d ragdb \
  --clean --if-exists /tmp/backup_20260710.dump
```

---

## 9. 升级策略

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 构建新镜像
docker compose build api worker

# 3. 滚动更新（不中断服务）
docker compose up -d --no-deps api worker

# 4. 执行数据库迁移
docker compose exec api alembic upgrade head

# 5. 验证
curl http://localhost:8000/health
```

---

## 10. 常用运维命令速查

```bash
# === 启动/停止 ===
docker compose up -d                      # 后台启动所有服务
docker compose down                       # 停止所有服务
docker compose down -v                    # ⚠️ 停止并删除所有数据
docker compose restart api                # 重启 API 服务

# === 查看状态 ===
docker compose ps                         # 服务状态
docker compose top                        # 进程信息
docker compose stats                      # 资源使用（CPU/内存）

# === 日志 ===
docker compose logs -f api                # 实时日志
docker compose logs --tail=100 api        # 最近 100 行

# === 调试 ===
docker compose exec api bash              # 进入 API 容器
docker compose exec postgres psql -U raguser ragdb  # 进入数据库

# === 迁移 ===
docker compose exec api alembic upgrade head       # 执行迁移
docker compose exec api alembic current            # 查看当前版本
docker compose exec api alembic history            # 迁移历史

# === 清理 ===
docker system prune -f                    # 清理未使用的镜像和容器
docker compose down --rmi all             # 停止并删除镜像
```
