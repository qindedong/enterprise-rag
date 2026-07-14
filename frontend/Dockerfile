# ============================================================
# 前端 Dockerfile — 多阶段构建
# ============================================================
# 构建命令:
#   docker build -t rag-frontend:latest -f frontend/Dockerfile .
# 运行命令:
#   docker run -d -p 80:80 rag-frontend:latest
# ============================================================

# ===== 阶段 1: 构建前端 =====
FROM node:22-alpine AS builder

WORKDIR /build

# 安装依赖
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --registry=https://registry.npmmirror.com

# 复制源码并构建
COPY frontend/ ./
RUN npm run build

# ===== 阶段 2: Nginx 静态服务 =====
FROM nginx:1.27-alpine

# 移除默认配置
RUN rm /etc/nginx/conf.d/default.conf

# 复制 Nginx 配置
COPY backend/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 复制前端构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://localhost/health-check || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
