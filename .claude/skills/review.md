# Code Review 技能 (Review)

## 描述
当用户提交代码变更或请求代码审查时，进行系统化的代码审查，关注正确性、性能、安全性和可维护性。

## 触发条件
- 用户提到"review"、"代码审查"、"检查代码"
- 用户提交了新的代码变更
- 合并前需要代码审查

## Code Review 流程

### 1. 审查维度

每次 Code Review 从以下维度进行检查：

| 维度 | 权重 | 检查要点 |
|------|------|---------|
| 正确性 | ★★★★★ | 逻辑是否正确、边界条件处理、异常处理 |
| 性能 | ★★★★☆ | 数据库查询效率、算法复杂度、资源使用 |
| 安全性 | ★★★★★ | 注入防护、认证授权、敏感信息保护 |
| 可维护性 | ★★★☆☆ | 代码结构、命名规范、注释完整性 |
| 可测试性 | ★★★☆☆ | 依赖注入、接口隔离、测试覆盖 |
| 一致性 | ★★☆☆☆ | 与现有代码风格一致、符合项目规范 |

### 2. 审查清单

#### 正确性检查
- [ ] 业务逻辑是否正确实现需求
- [ ] 边界条件是否处理（空值、零值、最大值）
- [ ] 异常路径是否有合适的错误处理
- [ ] 并发场景是否考虑竞态条件
- [ ] 事务边界是否合理
- [ ] 数据一致性是否有保证

#### 性能检查
- [ ] 数据库查询是否有 N+1 问题
- [ ] 是否使用了合适的索引
- [ ] 大数据量处理是否有分批/流式方案
- [ ] 是否有不必要的 I/O 操作
- [ ] 缓存策略是否合理
- [ ] 异步操作是否正确使用（async/await）

#### 安全检查
- [ ] 用户输入是否经过验证和清洗
- [ ] SQL 注入防护（使用参数化查询）
- [ ] XSS 防护（输出编码）
- [ ] 敏感信息是否加密存储
- [ ] API 是否有适当的认证和授权
- [ ] 文件上传是否有类型和大小限制
- [ ] 日志中是否包含敏感信息

#### Python/FastAPI 专项检查
```python
# ❌ 常见问题示例

# 1. 同步阻塞操作
def get_user(user_id: str):
    user = db.query(User).filter(User.id == user_id).first()  # 同步查询阻塞事件循环
    return user

# 2. 未处理的异常
@router.post("/upload")
async def upload(file: UploadFile):
    content = await file.read()
    result = process(content)  # 如果 process 抛异常，没有错误响应
    return result

# 3. 密码明文日志
logger.info(f"用户登录: {username}, 密码: {password}")  # 密码泄露

# 4. N+1 查询
documents = await db.execute(select(Document))
for doc in documents:  # 每个文档又触发一次查询
    chunks = await db.execute(
        select(DocumentChunk).where(DocumentChunk.document_id == doc.id)
    )

# ✅ 改进示例
async def get_user(user_id: str):
    query = select(User).where(User.id == user_id)
    result = await db.execute(query)  # 异步查询
    return result.scalar_one_or_none()

@router.post("/upload")
async def upload(file: UploadFile):
    try:
        content = await file.read()
        result = await process(content)
        return APIResponse(data=result)
    except ProcessingError as e:
        raise HTTPException(status_code=400, detail=str(e))

logger.info(f"用户登录: {username}")  # 不记录密码

# 使用 joinedload 预加载关联数据
query = select(Document).options(joinedload(Document.chunks))
documents = (await db.execute(query)).unique().scalars().all()
```

### 3. 审查报告模板

```markdown
# Code Review 报告

## 基本信息
- **审查时间**：{date}
- **审查分支**：{branch}
- **变更文件数**：{file_count}
- **变更行数**：+{additions} -{deletions}

## 总体评价
{summary}

## 发现的问题

### 🔴 严重问题（必须修复）
| # | 文件 | 行号 | 问题描述 | 建议修复 |
|---|------|------|---------|---------|
| 1 | xxx.py | 42 | ... | ... |

### 🟡 建议改进（推荐修复）
| # | 文件 | 行号 | 问题描述 | 建议修复 |
|---|------|------|---------|---------|
| 1 | xxx.py | 15 | ... | ... |

### 🟢 优秀实践（值得肯定）
- ...

## 性能分析
{perf_analysis}

## 安全检查
{security_check}

## 审查结论
- [ ] ✅ 通过（无严重问题）
- [ ] ⚠️ 有条件通过（建议修复后再合并）
- [ ] ❌ 需要重新审查（存在严重问题）
```

### 4. 自动化检查集成

```python
# 建议在 CI/CD 中集成的检查工具
PRE_COMMIT_CHECKS = {
    "代码格式": "ruff format --check .",
    "代码检查": "ruff check .",
    "类型检查": "mypy .",
    "安全检查": "bandit -c pyproject.toml -r .",
    "测试运行": "pytest --cov --cov-report=term-missing",
}

# .pre-commit-config.yaml
"""
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  
  - repo: https://github.com/python/mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, sqlalchemy]
"""
```
