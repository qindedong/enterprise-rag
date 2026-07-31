# 更新日志 (Changelog)

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### Added
- **PDF 四层架构 P3**（视觉理解 + Agent 工具层 + 分层评测）：
  - `parsers/pdf/vision_extractor.py`：figure 节点按 bbox 区域渲染（200 DPI）
    → 多模态模型生成 ≤300 字图表描述，回填 figure_summary chunk；
    `VISION_ENABLED` / `VISION_MODEL` 开关，视觉 API 不可用降级保留占位
  - `LLMClient.generate_with_image`：OpenAI Compatible vision 格式图像理解
  - `agent/tools.py`：L4 五件套 — search_pdf（hybrid 检索 + kind/section/pages
    过滤）、read_page、extract_table（行列 JSON）、analyze_chart、quote_source
  - `agent/planner.py`：规则意图路由（simple/quote/chart/table/compare），
    简单问题直通现有管线零延迟；工具链未命中或异常自动回退常规问答；
    `AGENT_MAX_STEPS` 步数上限兜底
  - 新端点 `POST /knowledge-bases/{kb_id}/agent/chat`
  - `eval/run_layered_eval.py`：分层评测（L1 分类准确率+OCR CER、
    L2 标题 F1+表格结构正确率、L3 页码精准率+图表检出、L4 路由准确率），
    样本自动生成、全程离线
- **PDF 四层架构 P2**（OCR 路径 + Contextual Retrieval）：
  - `parsers/pdf/ocr_extractor.py`：扫描页 300 DPI 渲染 → RapidOCR 识别，
    输出与原生同构的 Block（bbox 坐标还原），平均置信度 <70% 告警；
    引擎不可用降级为空页不崩溃；OCR 无文字时保留图像块供 P3 视觉理解
  - `rag/contextual.py`：`Contextualizer` 并发（Semaphore=4）为每个 chunk
    生成 ≤60 字出处说明并注入文首（`[说明]\n正文`），LLM 失败自动保持原样；
    `CONTEXTUAL_RETRIEVAL_ENABLED` 开关控制
  - 端到端验证：扫描件合同 OCR 置信度 100%，7 个 chunk 全部注入上下文，
    引用携带页码 + 章节 + 条款号
- **PDF 四层架构 P1**（表格结构化 + 条款边界切片）：
  - `parsers/pdf/tables.py`：`find_tables` 检测线框表格 → 表头 + 行列结构化，
    表注关联（"表 2-1 xxx"），表内文本块归属表格不再进入段落流
  - 表格 chunk 结构化渲染（"行 N：列名=值"，数字绑定指标与年份），
    长表按行分组且每组重复表头
  - 条款边界切片：`第X条` 为不可断边界，短条款合并只在条款边界处发生，
    单条款 chunk 标注 `clause_no`（"第十二条"→"第12条"）
  - `document_chunks.metadata.table_id` + Qdrant payload 同步扩展
- **PDF 四层架构 P0**（`docs/pdf_pipeline_architecture.md`）：
  - L1 解析层：`parsers/pdf/classifier.py` 逐页分类（原生/扫描/图文混排），
    `native_extractor.py` 块级抽取（bbox 坐标 + 图像区域感知）
  - L2 结构还原：`structure.py` 页眉页脚过滤（跨页同位置重复剔除）、
    多栏重组、书签目录 + 启发式标题层级、合同条款号归一化（"第十二条"→"第12条"）
  - L3 语义切片：`rag/semantic_chunker.py` 按章节路径分组切片（不跨标题，
    段落边界二次切，章节前缀注入），chunk 携带页码/章节路径/类型/条款号
  - 入库：`document_chunks.page_number/section_title/metadata` 全面启用，
    Qdrant payload 扩展 page_start/page_end/section_path/kind/clause_no
- **引用溯源升级**：RAG 引用携带页码 + 章节路径（向量与 BM25 双路径对齐），
  LLM context 注入来源位置标注

---

## [2.1.0] — 2026-07-31

Sprint 8 收尾版本。全链路联调验证通过，性能优化与质量检查落地。

### Added
- **幻觉检测**：`QualityChecker` 质量检查器，含引用越界检测与内容匹配度检查
- **性能压测**：Locust 压测脚本 (`perf/locustfile.py` + `perf/run_load_test.py`)，
  100 并发 P95=6s < 15s（达标）
- **全链路冒烟脚本**：`scripts/e2e_smoke.py`，覆盖 PRD 12 个 P0 用户故事
  共 18 项检查（注册/登录/建库/上传/处理/统计/问答/引用/诚实回答/
  SSE 流式/多轮对话/删除同步/监控），可重复执行
- **PDF 复杂场景处理方案**：`docs/pdf_parser_roadmap.md`（目录提取、
  页眉页脚过滤、多栏排版、表格、OCR 分级落地规划）

### Changed
- **检索参数调优**：`RETRIEVAL_TOP_K` 50→20, `RERANK_TOP_K` 10→8，
  热缓存检索 P95 从 2465ms 降至 33ms
- **数据库性能索引**：新增 8 个关键索引（documents/conversations/messages/
  kb_members/knowledge_bases/api_keys），消除全表扫描
- **连接池优化**：`pool_recycle` 60→30min, 禁用 statement cache, 减小内存占用
- **Embedding 缓存**：查询向量结果复用，热缓存后单次向量化 < 10ms
- **本地 Embedding 离线模式**：`local_files_only=True`，避免 HuggingFace 超时
- **检索评估脚本**：`eval/run_eval.py` 命令行工具，支持三种检索模式
- **Worker 镜像共享构建**：`Dockerfile.worker` 改为基于 `rag-api:latest`
  复用全部依赖层，构建时间 ~25min → 秒级，磁盘占用减半（层共享）

### Fixed
- Worker 无法处理文档（Docker Hub 网络超时 → 本地离线启动）
- RAG 非流式端点 `db.commit()` → `db.close()` 避免连接池耗尽
- 多个旧 uvicorn `--reload` 进程占用端口导致启动失败

---


## [2.0.0] — 2026-07-24

v2.0 企业版。跨知识库检索、数据分析看板、开放 API Key、SSO 单点登录、
Kubernetes 部署全部交付。

### Added
- **数据分析看板**：`GET /api/v1/analytics/overview` 跨知识库聚合统计
  （总量、满意率、近 30 天问答趋势、各库明细排行，按权限隔离）；
  前端新增「数据看板」页（总量卡片 + 趋势图 + 明细表）与侧边栏导航
- **跨知识库检索**：`RAGService.retrieve_multi` 多库并发检索按分数归并，
  单库失败自动跳过；新端点 `POST /search/multi`、`POST /chat/multi/sync`
  （逐库 RBAC 校验）；问答页新增「全部知识库（跨库检索）」模式
- **开放 API Key**：`api_keys` 表（SHA-256 哈希存储）+ 创建/列表/吊销接口 +
  alembic 迁移；`Bearer rag_xxx` / `X-API-Key` 双通道认证，权限等同所属用户，
  支持过期时间与最近使用追踪
- **SSO 单点登录**：通用 OIDC 授权码流程（Keycloak / Authentik / Auth0 /
  Entra ID），`/auth/sso/login` + `/auth/sso/callback`，按邮箱自动开通账号
  并签发系统 JWT，302 跳回前端；登录页新增 SSO 按钮与回调页
- **Kubernetes 部署**：`k8s/` Kustomize 全套清单（api HPA 2-10 副本、worker、
  frontend、postgres/qdrant StatefulSet + PVC、redis、Ingress SSE 长连接
  优化）+ `docs/K8S.md` 部署指南

### Changed
- RAG 非流式问答重构：抽取 `_generate` 公共方法，`ask` 与 `ask_multi` 复用

---

## [1.5.0] — 2026-07-24

v1.5 增强版收官。在 v1.0.0（含提前交付的混合检索与多轮对话）之上，
补齐 v1.5 规划的全部剩余项：Word 解析、批量上传、反馈分析、RBAC。

### Added
- **Word 文档解析**：新增 `DocxParser`（python-docx），段落按标题层级映射为
  Markdown `#` 前缀（与分块器兼容），表格按行展开为 `列1 | 列2 | 列3`；
  上传白名单与 Worker MIME 映射同步接入 `.docx`
- **批量上传**：上传区支持多选文件与多文件拖拽，逐个显示进度条与
  成功/失败状态；前端文件白名单同步放开 `.docx`
- **反馈分析面板**：`GET /api/v1/knowledge-bases/{kb_id}/feedback/stats`
  返回满意率、近 30 天按天正负反馈趋势、最近 10 条负反馈明细；
  KB 详情页新增可折叠可视化面板（满意率 + 堆叠柱状趋势 + 负反馈卡片）
- **RBAC 权限强制执行**：知识库成员三级角色
  viewer（问答/检索/查看）→ editor（+上传/重处理）→ admin（+删文档），
  owner 全权，全局 admin/super_admin 放行；`require_kb_role` /
  `require_doc_role` / `require_role` 依赖工厂，已接线文档管理、
  RAG 问答（流式/同步）、独立检索、创建对话、反馈统计等接口

### Changed
- **问答/检索/文档接口强制登录 + 知识库成员权限校验**（此前只校验知识库存在）；
  非成员访问返回 403，未登录返回 401

---

## [1.0.0] — 2026-07-24

首个正式版本。MVP 全部功能交付，并提前落地了原 v1.5 规划的
混合检索与多轮对话增强（检索质量与对话体验的核心项）。

### Added
- **用户系统**：注册、登录、JWT Token 认证、Token 刷新
- **知识库管理**：创建、列表、详情、更新、删除、成员管理
- **文档管理**：上传（PDF/Markdown/TXT）、列表、详情、删除
- **文档处理管线**：自动解析 → 分块（500/100） → 向量化 → Qdrant 索引，
  分块同步落库 `document_chunks`（jieba 预分词 + tsvector 生成列）
- **RAG 问答**：查询改写 → 向量检索（Top-50） → 重排序（Top-10） → LLM 流式生成
- **混合检索**（原 v1.5 规划，提前交付）：BM25（PostgreSQL tsvector + jieba）
  与向量检索 RRF 融合，`POST /search` 支持 `vector|bm25|hybrid` 三种模式
- **多轮对话增强**（原 v1.5 规划，提前交付）：对话历史 Token 预算裁剪（1500 tokens /
  6 轮）、指代消解查询改写、历史注入生成、问答轮次自动落库
- **独立检索 API**：`POST /api/v1/knowledge-bases/{kb_id}/search`，只检索不生成，
  供效果评估与调试
- **检索效果评估**：36 条标注数据集（easy/medium/hard）+ Recall@K / MRR 评估脚本
  （`backend/scripts/evaluate_retrieval.py`），基线：vector Recall@5=1.000、
  hybrid MRR@10=0.972
- **引用溯源**：每个回答附带引用来源（文档名、页码、原文片段）
- **对话管理**：创建对话、历史记录、消息反馈
- **前端应用**：React + TypeScript + TailwindCSS，支持流式显示
- **Docker 部署**：Docker Compose 一键部署（Nginx + API + Worker + PG + Qdrant + Redis）
- **CI**：GitHub Actions（backend: Ruff lint/format + Pytest 覆盖率 75% 门槛；
  frontend: oxlint + Vite build）

### Fixed
- **Worker Redis 超时死循环**：`redis.asyncio` 的 `TimeoutError` 不继承内置
  `TimeoutError`，BRPOP 空轮询每秒刷 ERROR 且无法消费任务
- **文档状态永不更新**：Worker 通过 pub/sub 发布 `rag:doc_status`，但 API 端无订阅者；
  新增 `doc_status_subscriber` 后台任务落库文档状态
- **qdrant-client 版本漂移**：server 1.9 与 client ≥1.10 不兼容（`search()` 被移除），
  依赖锁定 `<1.10`
- 9 处异常链缺失（`raise ... from`）、`Base` 再导出误删防护等 lint 修复

---

## 版本规划

| 版本 | 状态 | 预计时间 | 核心主题 |
|------|:---:|------|------|
| v0.1 | ✅ | Sprint 1-2 | 项目骨架 + 基础设施 |
| v0.2 | ✅ | Sprint 3-4 | 文档引擎 + 前端基础 |
| v0.3 | ✅ | Sprint 5 | RAG 检索链路 |
| v0.4 | ✅ | Sprint 6-7 | RAG 生成 + 对话 + 前端 |
| v1.0.0 | ✅ | 2026-07-24 | MVP 发布（含混合检索 + 多轮对话） |
| v1.5.0 | ✅ | 2026-07-24 | RBAC + 反馈面板 + 批量上传 + Word 解析 |
| v2.0.0 | ✅ | 2026-07-24 | 跨知识库 + 数据看板 + API Key/SSO + K8s |

> 🔜 = 计划中 | 🚧 = 开发中 | ✅ = 已发布 | 📋 = 待规划

---

## 变更分类说明

| 分类 | 说明 |
|------|------|
| **Added** | 新增功能 |
| **Changed** | 现有功能的变更 |
| **Deprecated** | 即将移除的功能 |
| **Removed** | 已移除的功能 |
| **Fixed** | Bug 修复 |
| **Security** | 安全修复 |
