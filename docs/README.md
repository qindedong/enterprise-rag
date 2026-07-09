# 企业级智能知识库 RAG — 文档中心

> 基于检索增强生成（RAG）的企业级知识库 AI 平台。

---

## 📖 文档导航

### 产品与需求

| 文档 | 说明 | 目标读者 |
|------|------|---------|
| [PRD.md](./PRD.md) | 产品需求文档：用户画像、功能清单、业务流程图、RBAC矩阵、异常场景 | 所有人 |
| [ROADMAP.md](./ROADMAP.md) | 开发路线图：版本规划、Sprint 拆分、里程碑、风险应对 | 开发者、PM |

### 架构与设计

| 文档 | 说明 | 目标读者 |
|------|------|---------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 技术架构设计：C4 Model、时序图、分层架构、可观测性、安全架构 | 开发者 |
| [ADR.md](./ADR.md) | 架构决策记录：Qdrant、DDD、FastAPI、PostgreSQL 等 8 项决策及理由 | 开发者、架构师 |
| [DATABASE.md](./DATABASE.md) | 数据库设计：ER 图、状态机、完整表结构、索引、Qdrant Collection、备份策略 | 开发者 |

### 开发参考

| 文档 | 说明 | 目标读者 |
|------|------|---------|
| [API.md](./API.md) | API 接口文档：认证、知识库、文档、RAG 问答、对话、系统接口 | 前端开发者 |
| [TASKS.md](./TASKS.md) | 详细任务拆分：125 个 Task，含优先级、工时、依赖、验收标准 | 开发者 |
| [TEST_PLAN.md](./TEST_PLAN.md) | 测试计划：单元/集成/E2E/RAG 准确率/性能/安全测试 | 开发者、QA |

### 运维与协作

| 文档 | 说明 | 目标读者 |
|------|------|---------|
| [DEPLOYMENT.md](./DEPLOYMENT.md) | 部署文档：快速部署、配置、扩容、备份恢复、运维命令 | DevOps |
| [CONTRIBUTING.md](./CONTRIBUTING.md) | 贡献指南：环境搭建、分支策略、提交规范、Code Review 流程 | 贡献者 |
| [CHANGELOG.md](./CHANGELOG.md) | 变更日志：按版本记录所有重要变更 | 所有人 |

---

## 🗺️ 阅读顺序建议

### 新加入的开发者

```
PRD.md → ARCHITECTURE.md → ADR.md → DATABASE.md → API.md → TASKS.md
```

### 要开始编码的开发者

```
CONTRIBUTING.md → TASKS.md（找到自己的 Sprint）→ API.md → TEST_PLAN.md
```

### 要做 Code Review 的人

```
CONTRIBUTING.md → ARCHITECTURE.md（分层架构）→ ADR.md（关键决策）
```

### 面试准备

```
PRD.md（竞争分析、RBAC、异常场景、用户故事）
  → ARCHITECTURE.md（C4 Model、时序图、RAG Pipeline）
    → ADR.md（技术决策理由）
      → DATABASE.md（ER 图、状态机、删除策略）
```

---

## 📊 项目状态

| 版本 | 状态 | 预计时间 |
|------|:---:|------|
| v1.0 MVP | 🚧 规划中 | Sprint 1-8（16 周） |
| v1.5 增强版 | 📋 待规划 | Sprint 9-12（8 周） |
| v2.0 企业版 | 📋 待规划 | Sprint 13-16（8 周） |

---

## 📝 文档维护

- **负责人**：所有开发者
- **更新时机**：每个 Sprint 结束时更新相关文档
- **审核**：Sprint 8（MVP 发布前）统一审校所有文档
- **语言**：简体中文（技术术语保留英文）
