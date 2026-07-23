"""
安全工具模块 — 密码哈希和 JWT Token 管理
"""

from datetime import UTC, datetime, timedelta

import bcrypt
from jose import jwt

from app.core.config import get_settings

settings = get_settings()

# ===== 密码哈希 =====


def hash_password(plain_password: str) -> str:
    """对明文密码进行 bcrypt 哈希"""
    # bcrypt 要求输入为 bytes，且长度不能超过 72 字节
    password_bytes = plain_password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证明文密码是否与哈希值匹配"""
    password_bytes = plain_password.encode("utf-8")[:72]
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ===== JWT Token =====


def create_access_token(user_id: str, role: str) -> str:
    """生成 Access Token（24小时有效）"""
    expire = datetime.now(UTC) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: str) -> str:
    """生成 Refresh Token（7天有效）"""
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """解码并验证 JWT Token，返回 payload"""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
