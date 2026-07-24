"""
SSO（OIDC）认证 API 接口

路由：
    GET /api/v1/auth/sso/login    — 获取 IdP 授权跳转 URL
    GET /api/v1/auth/sso/callback — IdP 回调：code 换用户信息，签发系统 JWT
"""

import secrets

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_db
from app.core.logger import get_logger
from app.models.request_response.response import APIResponse
from app.repositories.user_repository import UserRepository
from app.services.oidc_service import OIDCService
from app.utils.security import create_access_token, create_refresh_token, hash_password

logger = get_logger(__name__)

router = APIRouter(prefix="/auth/sso", tags=["SSO 认证"])


@router.get("/login", summary="获取 SSO 登录跳转 URL")
async def sso_login():
    """返回 IdP 授权页 URL，前端重定向过去完成登录"""
    service = OIDCService()
    state = secrets.token_urlsafe(16)
    url = service.build_authorization_url(state)
    return APIResponse(data={"authorization_url": url, "state": state})


@router.get("/callback", summary="SSO 回调")
async def sso_callback(
    code: str = Query(..., description="IdP 授权码"),
    state: str | None = Query(None),
    db=Depends(get_db),
):
    """
    IdP 登录成功后的回调：授权码换用户信息，按邮箱查找或自动开通账号，
    返回与账号密码登录一致的 JWT 响应。
    """
    service = OIDCService()
    userinfo = await service.exchange_code(code)

    user_repo = UserRepository(db)
    user = await user_repo.find_by_email(userinfo["email"])

    if not user:
        # 自动开通账号：用户名取邮箱前缀（冲突时追加随机后缀），密码为随机不可用值
        base_username = userinfo["email"].split("@")[0][:40]
        username = base_username
        if await user_repo.find_by_username(username):
            username = f"{base_username}_{secrets.token_hex(3)}"
        user = await user_repo.create(
            username=username,
            email=userinfo["email"],
            hashed_password=hash_password(secrets.token_urlsafe(24)),
            display_name=userinfo.get("name") or base_username,
        )
        await db.commit()
        logger.info(f"SSO 自动开通账号: {user.email}")

    if not user.is_active:
        from app.core.exceptions import UnauthorizedException

        raise UnauthorizedException("账号已被禁用，请联系管理员")

    await user_repo.update_last_login(user.id)
    await db.commit()

    access_token = create_access_token(str(user.id), user.role.value)
    refresh_token = create_refresh_token(str(user.id))

    logger.info(f"SSO 登录成功: {user.username}")

    # 浏览器场景：携带 token 重定向回前端回调页
    from urllib.parse import urlencode

    from fastapi.responses import RedirectResponse

    from app.core.config import get_settings

    frontend = get_settings().FRONTEND_URL
    params = urlencode({"access_token": access_token, "refresh_token": refresh_token})
    return RedirectResponse(url=f"{frontend}/sso/callback?{params}", status_code=302)
