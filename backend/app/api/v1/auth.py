"""
认证 API 接口

路由：
    POST /api/v1/auth/register  — 用户注册
    POST /api/v1/auth/login     — 用户登录
    POST /api/v1/auth/refresh   — 刷新 Token
    GET  /api/v1/auth/me        — 获取当前用户信息
"""

from fastapi import APIRouter, Depends

from app.api.deps import get_auth_service, get_current_user
from app.models.database.user import User
from app.models.request_response.response import APIResponse
from app.services.auth_service import AuthService
from pydantic import BaseModel, Field, EmailStr

router = APIRouter(prefix="/auth", tags=["认证"])


# ===== 请求模型 =====

class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    display_name: str | None = Field(None, max_length=100, description="显示名称")


class LoginRequest(BaseModel):
    """用户登录请求"""
    email: str = Field(..., description="邮箱地址")
    password: str = Field(..., description="密码")


class RefreshRequest(BaseModel):
    """Token 刷新请求"""
    refresh_token: str = Field(..., description="Refresh Token")


# ===== 接口 =====

@router.post("/register", summary="用户注册", status_code=201)
async def register(
    req: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> APIResponse[dict]:
    """注册新用户"""
    user = await auth_service.register(
        username=req.username,
        email=req.email,
        password=req.password,
        display_name=req.display_name,
    )
    return APIResponse(
        code=201,
        message="注册成功",
        data={
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
    )


@router.post("/login", summary="用户登录")
async def login(
    req: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> APIResponse[dict]:
    """用户登录，返回 JWT Token"""
    result = await auth_service.login(email=req.email, password=req.password)
    return APIResponse(message="登录成功", data=result)


@router.post("/refresh", summary="刷新 Token")
async def refresh_token(
    req: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> APIResponse[dict]:
    """使用 Refresh Token 获取新的 Access Token"""
    result = await auth_service.refresh_token(req.refresh_token)
    return APIResponse(message="Token 刷新成功", data=result)


@router.get("/me", summary="获取当前用户信息")
async def get_me(
    current_user: User = Depends(get_current_user),
) -> APIResponse[dict]:
    """获取当前登录用户的信息"""
    return APIResponse(
        data={
            "id": str(current_user.id),
            "username": current_user.username,
            "email": current_user.email,
            "display_name": current_user.display_name,
            "role": current_user.role.value if current_user.role else "user",
            "is_active": current_user.is_active,
            "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        }
    )
