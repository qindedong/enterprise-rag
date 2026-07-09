# 贡献指南

> **文档版本**: v1.0

---

## 环境搭建

```bash
# 1. 克隆项目
git clone <repo-url> && cd enterprise-rag

# 2. 创建虚拟环境
python -m venv .venv && source .venv/bin/activate  # Linux/Mac
python -m venv .venv && .venv\Scripts\activate     # Windows

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 安装 pre-commit hooks
pre-commit install

# 5. 启动开发环境
docker compose up -d postgres qdrant redis
cp .env.template .env  # 编辑 .env 填写配置
alembic upgrade head
uvicorn app.main:app --reload
```

---

## 分支策略（Git Flow）

```
main              ← 生产分支，只接受来自 develop 的 PR
  └── develop     ← 开发分支，日常开发基准
        ├── feature/xxx  ← 功能分支（从 develop 切出，合并回 develop）
        ├── fix/xxx      ← 修复分支
        └── release/x.x  ← 发布分支
```

---

## 提交信息规范（Conventional Commits）

```
<type>(<scope>): <简短描述>

类型：
  feat     - 新功能
  fix      - 修复 Bug
  refactor - 重构（不改变功能）
  docs     - 文档变更
  test     - 测试相关
  chore    - 构建/工具/依赖变更
  perf     - 性能优化

示例：
  feat(auth): 添加 JWT Token 刷新接口
  fix(rag): 修复引用编号不匹配的问题
  docs(api): 更新 RAG 问答接口文档
  test(rag): 添加引用完整性校验测试
```

---

## Code Review 流程

1. 从 `develop` 创建 feature 分支
2. 完成开发 + 单元测试（覆盖率 ≥ 80%）
3. 运行 `black . && ruff check . && mypy app/ && pytest`
4. 提交 PR 到 `develop`
5. CI 自动检查（Black + Ruff + MyPy + Pytest）
6. Code Review（参考 review.md 检查清单）
7. 通过后合并到 `develop`

### Review 检查清单

- [ ] 代码符合 DDD 分层架构（project-context.md 铁律）
- [ ] Router 中没有业务逻辑
- [ ] 公共函数有完整 Type Hint 和 Google Docstring
- [ ] 异常使用 AppException 体系
- [ ] 返回使用统一 APIResponse 格式
- [ ] 没有重复代码

---

## 质量门禁

代码合并前必须通过：

```bash
black --check app/ tests/    # 格式化检查
ruff check app/ tests/       # Lint 检查
mypy app/                    # 类型检查
pytest --cov-fail-under=80   # 测试 + 覆盖率
```
