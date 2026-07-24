"""
OIDC SSO 服务

通用 OpenID Connect 授权码流程，兼容 Keycloak / Authentik / Auth0 / Entra ID 等
标准 OIDC Provider。流程：
    1. build_authorization_url → 前端重定向到 IdP 登录页
    2. IdP 回调携带 code → exchange_code 换取 userinfo（email/name）
    3. 按 email 查找或自动开通本地账号，签发系统 JWT
"""

from urllib.parse import urlencode

import httpx

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedException, ValidationException
from app.core.logger import get_logger

logger = get_logger(__name__)


class OIDCService:
    """OIDC 单点登录服务"""

    def __init__(self):
        self.settings = get_settings()

    def _check_enabled(self) -> None:
        if not self.settings.OIDC_ENABLED:
            raise ValidationException("SSO 未启用，请联系管理员配置 OIDC")
        if not all(
            [
                self.settings.OIDC_CLIENT_ID,
                self.settings.OIDC_AUTHORIZE_URL,
                self.settings.OIDC_TOKEN_URL,
                self.settings.OIDC_USERINFO_URL,
            ]
        ):
            raise ValidationException("OIDC 配置不完整")

    def build_authorization_url(self, state: str) -> str:
        """构造 IdP 授权跳转 URL"""
        self._check_enabled()
        params = {
            "client_id": self.settings.OIDC_CLIENT_ID,
            "redirect_uri": self.settings.OIDC_REDIRECT_URI,
            "response_type": "code",
            "scope": self.settings.OIDC_SCOPE,
            "state": state,
        }
        return f"{self.settings.OIDC_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str) -> dict:
        """
        授权码换取用户信息

        Returns:
            {"email": str, "name": str|None, "sub": str}

        Raises:
            UnauthorizedException: code 无效或 IdP 返回异常
        """
        self._check_enabled()

        async with httpx.AsyncClient(timeout=15) as client:
            # Step 1: code → token
            token_resp = await client.post(
                self.settings.OIDC_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": self.settings.OIDC_CLIENT_ID,
                    "client_secret": self.settings.OIDC_CLIENT_SECRET,
                    "redirect_uri": self.settings.OIDC_REDIRECT_URI,
                    "code": code,
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code != 200:
                logger.warning(f"OIDC token 交换失败: {token_resp.status_code}")
                raise UnauthorizedException("SSO 授权码无效或已过期")

            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise UnauthorizedException("SSO 返回缺少 access_token")

            # Step 2: token → userinfo
            userinfo_resp = await client.get(
                self.settings.OIDC_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code != 200:
                raise UnauthorizedException("获取 SSO 用户信息失败")

        userinfo = userinfo_resp.json()
        email = userinfo.get("email")
        if not email:
            raise UnauthorizedException("SSO 账号未绑定邮箱，无法登录")

        return {
            "email": email,
            "name": userinfo.get("name") or userinfo.get("preferred_username"),
            "sub": userinfo.get("sub", ""),
        }
