# Kubernetes 部署指南

企业知识库 RAG 的 K8s 部署清单位于 `k8s/`，使用 Kustomize 组织。

## 架构

| 组件 | 资源 | 副本 | 说明 |
|------|------|------|------|
| frontend | Deployment + Service | 2 | Nginx 托管前端静态产物 |
| api | Deployment + Service + HPA | 2-10 | FastAPI，按 CPU 70% 自动扩缩 |
| worker | Deployment | 2 | 文档异步处理（解析/分块/向量化） |
| postgres | StatefulSet + Service + PVC(20Gi) | 1 | PostgreSQL 16 + pgvector |
| qdrant | StatefulSet + Service + PVC(20Gi) | 1 | 向量数据库 |
| redis | Deployment + Service | 1 | 队列 + 缓存 |
| ingress | Ingress | — | 域名入口，SSE 长连接超时已配置 |

`api` 与 `worker` 共享 `rag-uploads` PVC（需 **ReadWriteMany** 的
StorageClass，如 NFS / cephfs / 云厂商文件存储）。

## 部署步骤

### 1. 构建并推送镜像

```bash
# 后端 API（backend/Dockerfile）
docker build -t registry.example.com/enterprise-rag-api:latest backend/
# Worker（backend/Dockerfile.worker）
docker build -f backend/Dockerfile.worker -t registry.example.com/enterprise-rag-worker:latest backend/
# 前端（frontend 构建产物 + nginx）
docker build -t registry.example.com/enterprise-rag-frontend:latest frontend/

docker push registry.example.com/enterprise-rag-api:latest
docker push registry.example.com/enterprise-rag-worker:latest
docker push registry.example.com/enterprise-rag-frontend:latest
```

然后替换 `k8s/api.yaml`、`k8s/worker.yaml`、`k8s/frontend.yaml` 中的
`registry.example.com/...` 镜像地址。

### 2. 配置敏感信息

编辑 `k8s/secret.yaml` 填入真实值（**不要提交到 git**），或更安全地：

```bash
kubectl create namespace enterprise-rag
kubectl create secret generic rag-secret -n enterprise-rag \
  --from-literal=POSTGRES_USER=raguser \
  --from-literal=POSTGRES_PASSWORD='<强密码>' \
  --from-literal=JWT_SECRET_KEY='<随机长字符串>' \
  --from-literal=LLM_API_KEY='<你的 LLM Key>'
```

`k8s/configmap.yaml` 中按需调整域名（`FRONTEND_URL`）、OIDC 等配置；
`k8s/ingress.yaml` 中替换 `rag.example.com` 为实际域名。

### 3. 一键部署

```bash
kubectl apply -k k8s/
```

### 4. 数据库迁移

首次部署后执行 Alembic 迁移（任选一只 api Pod）：

```bash
kubectl exec -it deploy/api -n enterprise-rag -- alembic upgrade head
```

### 5. 验证

```bash
kubectl get pods -n enterprise-rag
curl https://rag.example.com/api/v1/health
```

## 开启 SSO（可选）

在 `configmap.yaml` 设置 `OIDC_ENABLED: "true"` 并填写 IdP 的
authorize/token/userinfo 端点；`secret.yaml` 填入
`OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET`；IdP 侧回调地址配置为
`https://rag.example.com/api/v1/auth/sso/callback`，然后
`kubectl rollout restart deploy/api -n enterprise-rag`。

## 生产建议

- **数据库外置**：生产环境建议用云 RDS / 云向量库替代集群内
  StatefulSet，修改 `configmap.yaml` 中连接地址即可。
- **TLS**：配合 cert-manager 取消 `ingress.yaml` 中 TLS 注释。
- **监控**：可追加 Prometheus ServiceMonitor 抓取 api 指标，
  Grafana 看板与数据看板 API（`/api/v1/analytics/overview`）互补。
