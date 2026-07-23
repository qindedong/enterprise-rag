"""
用户数据访问层

封装所有用户相关的数据库查询，不包含任何业务逻辑.
"""

from datetime import UTC
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database.user import User


class UserRepository:
    """用户数据访问层"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, username: str, email: str, hashed_password: str, display_name: str | None = None
    ) -> User:
        """创建用户"""
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            display_name=display_name or username,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def find_by_id(self, user_id: UUID) -> User | None:
        """按 ID 查找用户"""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        """按邮箱查找用户"""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def find_by_username(self, username: str) -> User | None:
        """按用户名查找用户"""
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def update_last_login(self, user_id: UUID) -> None:
        """更新最后登录时间"""
        from datetime import datetime

        from sqlalchemy import update

        await self.session.execute(
            update(User).where(User.id == user_id).values(last_login_at=datetime.now(UTC))
        )
