"""
认证服务

负责用户注册、登录、Token 刷新的业务逻辑编排.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DuplicateException, UnauthorizedException, ValidationException
from app.core.logger import get_logger
from app.models.database.user import User
from app.repositories.user_repository import UserRepository
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = get_logger(__name__)


class AuthService:
    """认证服务"""

    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register(
        self, username: str, email: str, password: str, display_name: str | None = None
    ) -> User:
        """
        用户注册

        Args:
            username: 用户名（3-50字符）
            email: 邮箱（唯一）
            password: 明文密码（8-128字符）
            display_name: 显示名称（默认同 username）

        Returns:
            新创建的用户对象

        Raises:
            DuplicateException: 用户名或邮箱已存在
            ValidationException: 输入格式不符合要求
        """
        # 校验用户名
        if await self.user_repo.find_by_username(username):
            raise DuplicateException("用户名", f"username={username}")

        # 校验邮箱
        if await self.user_repo.find_by_email(email):
            raise DuplicateException("邮箱", f"email={email}")

        # 密码强度校验
        if len(password) < 8 or len(password) > 128:
            raise ValidationException("密码长度必须为 8-128 个字符")

        # 创建用户
        hashed = hash_password(password)
        user = await self.user_repo.create(
            username=username,
            email=email,
            hashed_password=hashed,
            display_name=display_name,
        )

        logger.info(f"用户注册成功: {user.username} ({user.id})")
        return user

    async def login(self, email: str, password: str) -> dict:
        """
        用户登录

        Args:
            email: 邮箱
            password: 明文密码

        Returns:
            包含 access_token、refresh_token 和用户信息的字典

        Raises:
            UnauthorizedException: 邮箱或密码错误、账号禁用
        """
        # 查找用户
        user = await self.user_repo.find_by_email(email)
        if not user:
            raise UnauthorizedException("账号或密码错误")

        # 验证密码
        if not verify_password(password, user.hashed_password):
            raise UnauthorizedException("账号或密码错误")

        # 检查账号状态
        if not user.is_active:
            raise UnauthorizedException("账号已被禁用，请联系管理员")

        # 生成 Token
        access_token = create_access_token(str(user.id), user.role.value)
        refresh_token = create_refresh_token(str(user.id))

        # 更新登录时间
        await self.user_repo.update_last_login(user.id)

        logger.info(f"用户登录成功: {user.username}")
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 86400,
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role.value,
            },
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """
        刷新 Access Token

        Args:
            refresh_token: 有效的 Refresh Token

        Returns:
            新的 access_token 和 refresh_token

        Raises:
            UnauthorizedException: Token 无效或过期
        """
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise UnauthorizedException("无效的 Refresh Token")
        except Exception:
            raise UnauthorizedException("Refresh Token 无效或已过期")

        user_id = payload["sub"]
        user = await self.user_repo.find_by_id(user_id)
        if not user or not user.is_active:
            raise UnauthorizedException("用户不存在或已被禁用")

        new_access_token = create_access_token(str(user.id), user.role.value)
        new_refresh_token = create_refresh_token(str(user.id))

        logger.info(f"Token 刷新成功: {user.username}")
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": 86400,
        }

    async def get_current_user(self, user_id: str) -> User:
        """
        获取当前登录用户

        Args:
            user_id: 用户 UUID 字符串

        Returns:
            User 对象

        Raises:
            UnauthorizedException: 用户不存在或已禁用
        """
        from uuid import UUID

        user = await self.user_repo.find_by_id(UUID(user_id))
        if not user or not user.is_active:
            raise UnauthorizedException("用户不存在或已被禁用")
        return user
