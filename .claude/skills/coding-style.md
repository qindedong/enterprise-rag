# 编码风格规范 (Coding Style)

## 描述
**强制技能**。定义本项目的编码风格标准。所有 Python 代码必须严格遵循此规范。

## 触发条件
- **始终触发**：任何 Python 代码的编写、修改操作
- 用户提到"代码风格"、"格式化"、"类型注解"、"注释规范"

---

## 一、PEP8 规范（强制）

### 1. 基本格式

```python
# 缩进：4 个空格（严禁使用 Tab）
# 行宽：100 字符（Black 默认）
# 文件编码：UTF-8

# 文件头部
"""模块文档字符串 — 描述模块的职责和主要内容"""

```

### 2. 导入顺序（isort 风格）

```python
# 第一组：标准库
import asyncio
import os
from pathlib import Path
from typing import Optional, Union

# 第二组：第三方库
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

# 第三组：本地模块
from app.core.config import Settings
from app.core.exceptions import NotFoundException
from app.models.response import APIResponse
from app.services.document_service import DocumentService
```

### 3. 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 模块/文件 | snake_case | `document_service.py` |
| 类名 | PascalCase | `DocumentService`, `RAGQuery` |
| 函数/方法 | snake_case | `upload_document()`, `find_by_id()` |
| 变量 | snake_case | `doc_count`, `chunk_size` |
| 常量 | UPPER_SNAKE_CASE | `MAX_FILE_SIZE`, `DEFAULT_CHUNK_SIZE` |
| 私有成员 | _前缀 | `_validate_file()`, `_internal_cache` |
| 布尔变量 | is_/has_/can_ 前缀 | `is_processed`, `has_metadata`, `can_delete` |

---

## 二、Type Hint 类型注解（强制）

### 1. 所有公共函数必须有完整类型注解

```python
# ❌ 错误 — 没有类型注解
def process_document(file, chunk_size=512):
    ...

# ❌ 错误 — 类型注解不完整
def process_document(file: UploadFile, chunk_size) -> DocumentResponse:
    ...

# ✅ 正确 — 完整的类型注解
async def process_document(
    file: UploadFile,
    chunk_size: int = 512,
    strategy: str = "semantic"
) -> DocumentResponse:
    ...
```

### 2. 复杂类型的注解

```python
from typing import Optional, Union, Any, TypeVar, Generic

# 可选类型
def find_document(doc_id: str) -> Optional[Document]:
    """返回 None 表示文档不存在"""

# 联合类型
def process_input(data: Union[str, bytes, Path]) -> str:
    """接受多种输入类型"""

# 泛型
T = TypeVar("T")

class Repository(Generic[T]):
    async def find_by_id(self, id: str) -> Optional[T]: ...

# 可调用对象
from collections.abc import Callable, Awaitable

Handler = Callable[[Document], Awaitable[None]]
```

### 3. 容器类型注解（Python 3.12+ 语法）

```python
# ✅ 使用 Python 3.12+ 简洁语法
def batch_process(docs: list[Document]) -> dict[str, int]:
    """返回 {doc_id: chunk_count}"""

def get_tags(doc_id: str) -> set[str]:
    """返回文档标签集合"""

def group_by_type(docs: list[Document]) -> dict[str, list[Document]]:
    """按类型分组文档"""
```

### 4. 不允许的类型注解

```python
# ❌ 禁止使用 Any 偷懒（除非确实无法确定类型）
def process(data: Any) -> Any:  # ❌
    ...

# ✅ 如果确实需要 Any，添加注释说明原因
def process(data: Any) -> Any:  # 兼容旧版 API 的过渡期方案，TODO: v2.0 移除
    ...
```

---

## 三、Google Docstring（强制）

### 1. 模块文档

```python
"""
文档管理服务模块

本模块负责文档的完整生命周期管理：
- 文档上传与解析
- 文档分块与向量化
- 文档检索与删除

核心类:
    DocumentService: 文档管理主服务
    DocumentParser: 文档解析器

使用示例:
    service = DocumentService(doc_repo, chunk_repo, embedding_service)
    result = await service.upload_document(file)
"""
```

### 2. 类文档

```python
class DocumentService:
    """
    文档管理业务服务

    负责文档上传、解析、分块、向量化的完整流程编排。

    Attributes:
        doc_repo: 文档数据访问层
        chunk_repo: 分块数据访问层
        embedding_service: 向量化服务
        parser_factory: 文档解析器工厂，根据文件类型选择合适的解析器

    Examples:
        >>> service = DocumentService(doc_repo, chunk_repo, emb_service)
        >>> result = await service.upload_document(file)
        >>> print(result.id)
    """
```

### 3. 函数/方法文档

```python
async def upload_document(
    self,
    file: UploadFile,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> DocumentResponse:
    """
    上传并处理文档

    流程：
    1. 校验文件类型和大小
    2. 检查内容是否重复
    3. 创建文档记录
    4. 解析文档内容
    5. 智能分块
    6. 向量化并存入向量数据库

    Args:
        file: 要上传的文件对象
        chunk_size: 分块大小（token数），默认512
        chunk_overlap: 分块重叠大小（token数），默认64

    Returns:
        DocumentResponse: 包含文档ID、状态、分块数等信息的响应对象

    Raises:
        ValidationException: 文件类型不支持或大小超限
        DuplicateException: 相同内容的文档已存在
        ProcessingException: 文档解析或向量化失败

    Note:
        大文件（>50MB）会自动切换到流式处理模式
    """
```

---

## 四、代码格式化工具配置（强制）

### 1. Black 配置

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py312']
include = '\.pyi?$'
extend-exclude = '''
/(
    \.eggs
  | \.git
  | \.venv
  | build
  | dist
)/
'''
```

```bash
# 格式化命令
black .
black --check .  # 只检查，不修改
```

### 2. Ruff 配置

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
    "E",   # pycodestyle 错误
    "F",   # pyflakes
    "I",   # isort 导入排序
    "N",   # pep8-naming 命名规范
    "W",   # pycodestyle 警告
    "UP",  # pyupgrade 新版语法
    "B",   # flake8-bugbear 常见陷阱
    "C4",  # flake8-comprehensions 推导式优化
    "SIM", # flake8-simplify 代码简化
    "RUF", # Ruff 专属规则
]
ignore = [
    "E501",  # 行宽由 Black 处理
]

[tool.ruff.lint.isort]
known-first-party = ["app"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

```bash
# 检查
ruff check .
# 自动修复
ruff check --fix .
# 格式化
ruff format .
```

### 3. MyPy 配置

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true

[[tool.mypy.overrides]]
module = [
    "tests.*",
]
disallow_untyped_defs = false
```

```bash
# 类型检查
mypy app/
```

---

## 五、代码质量检查清单

### 提交前必须通过以下检查

```bash
# 1. 格式化检查
black --check app/ tests/

# 2. Lint 检查
ruff check app/ tests/

# 3. 类型检查
mypy app/

# 4. 测试全部通过
pytest -v
```

### 代码 Review 时必查项

- [ ] 所有公共函数是否有完整的 Type Hint？
- [ ] 所有公共函数/类是否有 Google Docstring？
- [ ] 命名是否符合规范（snake_case / PascalCase）？
- [ ] 导入顺序是否正确（标准库 → 第三方 → 本地）？
- [ ] 是否存在 `type: ignore` 或 `Any` 偷懒？（需要的话必须有注释说明）
- [ ] 代码是否能通过 Black + Ruff + MyPy？
- [ ] 新代码风格是否与现有代码一致？
- [ ] 是否存在魔法数字？（应定义为常量）
- [ ] 单个函数是否过长？（超过 50 行应考虑拆分）

---

## 六、常见反模式（禁止）

```python
# ❌ 反模式 1：裸 except
try:
    result = await process()
except:  # ❌ 会吞掉 KeyboardInterrupt 和 SystemExit
    pass

# ✅ 正确
try:
    result = await process()
except ProcessingException as e:
    logger.error(f"处理失败: {e}")

# ❌ 反模式 2：可变默认参数
def add_tags(doc_id: str, tags: list[str] = []):  # ❌
    tags.append("default")
    ...

# ✅ 正确
def add_tags(doc_id: str, tags: list[str] | None = None):
    tags = tags or []
    tags.append("default")
    ...

# ❌ 反模式 3：字符串拼接 SQL
query = f"SELECT * FROM documents WHERE title = '{title}'"  # ❌ SQL 注入风险

# ✅ 正确
result = await session.execute(select(Document).where(Document.title == title))

# ❌ 反模式 4：在循环中 await（应并行）
for doc in documents:
    await process_document(doc)  # ❌ 串行执行

# ✅ 正确
await asyncio.gather(*[process_document(doc) for doc in documents])
```
