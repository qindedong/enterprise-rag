# 单元测试技能 (Testing)

## 描述
当用户需要编写单元测试、集成测试或评估测试覆盖率时，提供专业的测试指导。

## 触发条件
- 用户提到"测试"、"单元测试"、"pytest"、"测试用例"
- 用户需要编写或修改测试代码
- 用户询问如何提高测试覆盖率

## 测试策略

### 1. 测试金字塔

```
         ╱  E2E 测试 ╲          ← 少量，验证核心用户流程
        ╱──────────────╲
       ╱   集成测试      ╲        ← 中等，验证模块间协作
      ╱──────────────────╲
     ╱     单元测试        ╲      ← 大量，验证单个函数/方法
    ╱────────────────────────╲
```

- **单元测试**（70%）：测试独立的函数、类方法
- **集成测试**（20%）：测试 API 端点、数据库操作、外部服务交互
- **E2E 测试**（10%）：测试完整的用户操作流程

### 2. 测试框架和工具

```python
# requirements-dev.txt
pytest==8.0.0
pytest-asyncio==0.23.0
pytest-cov==4.1.0
pytest-mock==3.12.0
httpx==0.26.0           # FastAPI 测试客户端
factory-boy==3.3.0      # 测试数据工厂
faker==22.0.0           # 假数据生成
```

### 3. 测试项目结构

```
tests/
├── conftest.py                 # 全局 fixtures
├── factories/                  # 测试数据工厂
│   ├── __init__.py
│   ├── document_factory.py
│   └── kb_factory.py
├── unit/                       # 单元测试
│   ├── services/
│   │   ├── test_document_service.py
│   │   ├── test_rag_service.py
│   │   └── test_retrieval_service.py
│   ├── utils/
│   │   ├── test_text_splitter.py
│   │   └── test_embedding.py
│   └── models/
│       └── test_domain_models.py
├── integration/                # 集成测试
│   ├── api/
│   │   ├── test_document_api.py
│   │   ├── test_rag_api.py
│   │   └── test_search_api.py
│   └── database/
│       ├── test_document_repo.py
│       └── test_vector_store.py
└── e2e/                        # 端到端测试
    ├── test_upload_and_query.py
    └── test_multiround_conversation.py
```

### 4. Pytest 配置

```python
# pyproject.toml 中的 pytest 配置
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
addopts = [
    "-v",
    "--strict-markers",
    "--cov=app",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=80",
]
markers = [
    "unit: 单元测试",
    "integration: 集成测试（需要数据库等外部依赖）",
    "e2e: 端到端测试",
    "slow: 运行较慢的测试",
]
```

### 5. 全局 Fixtures

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.main import app
from app.core.config import get_settings
from app.models.database import Base

# ===== 数据库 Fixtures =====

@pytest_asyncio.fixture
async def test_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    """创建测试数据库会话"""
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()

# ===== HTTP 客户端 Fixtures =====

@pytest_asyncio.fixture
async def client():
    """创建异步 HTTP 测试客户端"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

# ===== Mock Fixtures =====

@pytest.fixture
def mock_llm_service(mocker):
    """Mock LLM 服务（避免实际调用 API）"""
    mock = mocker.patch("app.services.llm_service.LLMService.generate")
    mock.return_value = "这是一个模拟的 LLM 回答"
    return mock

@pytest.fixture
def mock_embedding_service(mocker):
    """Mock Embedding 服务"""
    mock = mocker.patch("app.services.embedding_service.EmbeddingService.embed")
    mock.return_value = [0.1] * 1536  # 返回固定维度的假向量
    return mock

@pytest.fixture
def sample_document():
    """示例文档数据"""
    return {
        "title": "测试文档",
        "file_type": "md",
        "content": "这是一份测试文档的内容，用于单元测试。",
    }
```

### 6. 单元测试示例

```python
# tests/unit/services/test_rag_service.py
import pytest
from unittest.mock import AsyncMock

from app.services.rag_service import RAGService
from app.models.domain import RAGQuery, RAGResponse

@pytest.mark.unit
class TestRAGService:
    """RAG 服务单元测试"""
    
    @pytest.mark.asyncio
    async def test_query_returns_answer_with_citations(
        self,
        db_session,
        mock_embedding_service,
        mock_llm_service,
    ):
        """测试：RAG 查询返回带引用的答案"""
        # 准备
        service = RAGService(
            db=db_session,
            embedding_service=mock_embedding_service,
            llm_service=mock_llm_service,
        )
        query = RAGQuery(
            question="什么是企业知识库？",
            kb_id="test-kb-001",
        )
        
        # 执行
        result = await service.query(query)
        
        # 断言
        assert isinstance(result, RAGResponse)
        assert result.answer is not None
        assert len(result.answer) > 0
        assert isinstance(result.citations, list)
        assert result.token_usage is not None
    
    @pytest.mark.asyncio
    async def test_query_with_no_relevant_docs_returns_unknown(
        self,
        db_session,
        mock_embedding_service,
    ):
        """测试：无相关文档时返回"无法回答"提示"""
        mock_embedding_service.return_value = []  # 无检索结果
        service = RAGService(
            db=db_session,
            embedding_service=mock_embedding_service,
            llm_service=AsyncMock(),
        )
        query = RAGQuery(question="非常生僻的问题", kb_id="test-kb-001")
        
        result = await service.query(query)
        
        assert "无法回答" in result.answer or "未找到" in result.answer
    
    @pytest.mark.asyncio
    async def test_query_with_empty_question_raises_error(
        self,
        db_session,
    ):
        """测试：空问题抛出验证错误"""
        service = RAGService(db=db_session, embedding_service=AsyncMock(), llm_service=AsyncMock())
        
        with pytest.raises(ValueError, match="问题不能为空"):
            await service.query(RAGQuery(question="", kb_id="test-kb-001"))

@pytest.mark.unit
class TestTextSplitter:
    """文本分块器单元测试"""
    
    def test_split_by_fixed_size(self):
        """测试：固定大小分块"""
        from app.utils.text_splitter import TextSplitter
        
        splitter = TextSplitter(chunk_size=100, chunk_overlap=20)
        text = "这是一段测试文本。" * 50
        chunks = splitter.split(text)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100
    
    def test_split_empty_text_returns_empty(self):
        """测试：空文本分块返回空列表"""
        from app.utils.text_splitter import TextSplitter
        
        splitter = TextSplitter()
        chunks = splitter.split("")
        
        assert chunks == []
    
    def test_chunk_overlap(self):
        """测试：分块之间的重叠部分"""
        from app.utils.text_splitter import TextSplitter
        
        splitter = TextSplitter(chunk_size=50, chunk_overlap=10)
        text = "abcdefghij" * 20
        chunks = splitter.split(text)
        
        # 验证相邻分块有重叠
        if len(chunks) >= 2:
            first_end = chunks[0][-10:]
            second_start = chunks[1][:10]
            assert first_end == second_start
```

### 7. 集成测试示例

```python
# tests/integration/api/test_rag_api.py
import pytest
from httpx import AsyncClient

@pytest.mark.integration
class TestRAGAPI:
    """RAG API 集成测试"""
    
    @pytest.mark.asyncio
    async def test_ask_endpoint_returns_200(
        self,
        client: AsyncClient,
        db_session,
    ):
        """测试：问答接口返回 200"""
        response = await client.post(
            "/api/v1/rag/ask",
            json={
                "question": "公司年假有多少天？",
                "kb_id": "test-kb-001",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "answer" in data["data"]
    
    @pytest.mark.asyncio
    async def test_ask_without_question_returns_422(
        self,
        client: AsyncClient,
    ):
        """测试：缺少问题参数返回 422 验证错误"""
        response = await client.post(
            "/api/v1/rag/ask",
            json={"kb_id": "test-kb-001"},
        )
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_multiround_conversation(
        self,
        client: AsyncClient,
        db_session,
    ):
        """测试：多轮对话上下文保持"""
        # 第一轮问答
        resp1 = await client.post(
            "/api/v1/rag/ask",
            json={
                "question": "公司年假有多少天？",
                "kb_id": "test-kb-001",
                "conversation_id": None,
            },
        )
        conv_id = resp1.json()["data"]["conversation_id"]
        
        # 第二轮追问（省略主语）
        resp2 = await client.post(
            "/api/v1/rag/ask",
            json={
                "question": "怎么申请呢？",
                "kb_id": "test-kb-001",
                "conversation_id": conv_id,
            },
        )
        
        assert resp2.status_code == 200
        # 验证第二轮回答与年假申请相关
        answer = resp2.json()["data"]["answer"]
        assert "申请" in answer or "请假" in answer or "年假" in answer
```

### 8. 测试数据工厂

```python
# tests/factories/document_factory.py
import factory
from faker import Faker

fake = Faker("zh_CN")

class DocumentFactory(factory.Factory):
    """文档测试数据工厂"""
    class Meta:
        model = dict  # 或使用具体的 ORM 模型
    
    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    title = factory.LazyFunction(lambda: fake.sentence(nb_words=4))
    file_type = factory.Iterator(["pdf", "docx", "md", "txt"])
    file_size = factory.LazyFunction(lambda: fake.random_int(1024, 10485760))
    status = factory.Iterator(["pending", "processing", "completed"])
    chunk_count = factory.LazyFunction(lambda: fake.random_int(0, 100))
    created_at = factory.LazyFunction(lambda: fake.date_time_between(start_date="-30d"))
```

### 9. 测试运行命令

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest -m unit

# 运行集成测试
pytest -m integration

# 运行特定文件
pytest tests/unit/services/test_rag_service.py

# 运行特定测试
pytest tests/unit/services/test_rag_service.py::TestRAGService::test_query_returns_answer_with_citations

# 详细输出 + 覆盖率报告
pytest -v --cov=app --cov-report=html

# 并行运行（需要 pytest-xdist）
pytest -n auto

# 先运行上次失败的测试
pytest --lf

# 只运行新改动的测试（需要 pytest-testmon）
pytest --testmon
```
