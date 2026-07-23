"""
测试全局配置和 Fixtures

提供 SQLite 内存数据库 + FastAPI TestClient + 依赖覆盖。
所有测试在无外部依赖（PG/Redis/Qdrant）的环境下可运行。
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app


@pytest.fixture
def anyio_backend():
    """指定异步测试后端"""
    return "asyncio"


@pytest_asyncio.fixture
async def test_engine():
    """创建 SQLite 内存数据库（测试用）"""
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


@pytest_asyncio.fixture
async def override_get_db(test_engine):
    """用 SQLite 内存数据库覆盖 FastAPI 的 get_db 依赖

    所有通过 ASGITransport(app=app) 发送的 HTTP 请求，
    其 Depends(get_db) 都将使用 SQLite 而非真实 PostgreSQL。
    """
    session_factory = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async def _test_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_db] = _test_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(override_get_db):
    """创建异步 HTTP 测试客户端（使用 SQLite 替代真实 PG）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
