# 更新日志 (Changelog)

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### Added
- 项目初始化，创建基础目录结构

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
| v2.0.0 | 📋 | Sprint 13-16 | 跨知识库 + SSO + 数据面板 |

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
