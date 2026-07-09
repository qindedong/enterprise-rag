"""
Request ID 中间件

为每个 HTTP 请求注入唯一的 Request ID，用于全链路追踪。
- 优先使用客户端传入的 X-Request-ID
- 如果没有则自动生成 UUID
- 将 Request ID 附加到响应头

使用方式（在 main.py 中）:
    app.add_middleware(RequestIDMiddleware)
"""

import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Request ID 中间件 — 全链路追踪"""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
