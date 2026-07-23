"""
SQLAlchemy 异步引擎和会话管理

使用示例:
    from app.models.database.base import Base
    from app.core.database import async_session

    async with async_session() as session:
        result = await session.execute(select(User))
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# 异步引擎
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,  # 连接前检查有效性
    pool_recycle=3600,  # 连接回收时间（秒）
)

# 异步会话工厂
async_session = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # commit 后不使对象过期
)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类"""

    pass


# 确保所有模型被导入（供 Alembic autogenerate 使用）


async def get_db() -> AsyncSession:
    """获取数据库会话（依赖注入用）

    自动处理事务提交和回滚：
    - 正常结束：自动 commit
    - 发生异常：自动 rollback
    - 最终：自动 close

    Yields:
        AsyncSession: 数据库会话实例
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
