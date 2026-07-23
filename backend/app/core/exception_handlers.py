"""
全局异常处理器

将 AppException 及其子类转换为统一的 APIResponse 格式。
同时提供兜底的全局异常处理，防止未预期的异常泄露内部信息。

使用方式（在 main.py 中注册）:
    from app.core.exception_handlers import register_exception_handlers
    register_exception_handlers(app)
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logger import get_logger

logger = get_logger(__name__)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """统一处理所有 AppException 及其子类"""
    logger.warning(
        f"业务异常: [{exc.code}] {exc.message} | {exc.detail} | "
        f"请求: {request.method} {request.url.path}"
    )
    return JSONResponse(
        status_code=exc.code,
        content={
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail,
            "data": None,
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底异常处理 — 捕获所有未预期的异常"""
    logger.error(
        f"未处理异常: {type(exc).__name__}: {exc!s} | 请求: {request.method} {request.url.path}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "detail": "系统繁忙，请稍后重试",
            "data": None,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """向 FastAPI 应用注册异常处理器"""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)
    logger.info("异常处理器注册完成")
