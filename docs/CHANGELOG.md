# 更新日志 (Changelog)

本文件记录项目的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### Added
- 项目初始化，创建基础目录结构

---

## [1.0.0] — MVP 版本（计划中）

> 预计发布：Sprint 8 结束（第 16 周）

### Added
- **用户系统**：注册、登录、JWT Token 认证、Token 刷新
- **知识库管理**：创建、列表、详情、更新、删除、成员管理
- **文档管理**：上传（PDF/Markdown/TXT）、列表、详情、删除
- **文档处理管线**：自动解析 → 分块（500/100） → 向量化 → Qdrant 索引
- **RAG 问答**：查询改写 → 向量检索（Top-50） → 重排序（Top-10） → LLM 流式生成
- **引用溯源**：每个回答附带引用来源（文档名、页码、原文片段）
- **对话管理**：创建对话、历史记录、消息反馈
- **前端应用**：React + TypeScript + TailwindCSS，支持流式显示
- **Docker 部署**：Docker Compose 一键部署（Nginx + API + Worker + PG + Qdrant + Redis）
- **CI/CD**：GitHub Actions 自动运行 Black + Ruff + MyPy + Pytest

---

## 版本规划

| 版本 | 状态 | 预计时间 | 核心主题 |
|------|:---:|------|------|
| v0.1 | 🔜 | Sprint 1-2 | 项目骨架 + 基础设施 |
| v0.2 | 🔜 | Sprint 3-4 | 文档引擎 + 前端基础 |
| v0.3 | 🔜 | Sprint 5 | RAG 检索链路 |
| v0.4 | 🔜 | Sprint 6-7 | RAG 生成 + 对话 + 前端 |
| v1.0.0 | 🔜 | Sprint 8 | MVP 发布 |
| v1.5.0 | 📋 | Sprint 9-12 | 混合检索 + RBAC + 多轮对话 |
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
