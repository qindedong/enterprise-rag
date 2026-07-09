"""
统一异常体系

项目所有业务异常必须继承 AppException 基类。
禁止在代码中直接 raise HTTPException，必须使用本模块定义的异常类。

使用示例:
    from app.core.exceptions import NotFoundException, ValidationException

    raise NotFoundException("文档", doc_id)
    raise ValidationException("文件类型不支持")
"""

from typing import Any


class AppException(Exception):
    """应用异常基类

    所有业务异常必须继承此类，由全局异常处理器统一捕获并转换为标准响应格式。

    Attributes:
        code: HTTP 状态码
        message: 错误概要（展示给用户）
        detail: 错误详情（可选，用于调试）
    """

    def __init__(self, code: int, message: str, detail: str = ""):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


# ===== 客户端异常 (4xx) =====

class NotFoundException(AppException):
    """资源不存在异常 (404)

    当请求的资源（知识库、文档、对话等）在数据库中不存在时抛出。
    """

    def __init__(self, resource: str | None = None, identifier: str = ""):
        if resource:
            message = f"{resource}不存在"
            detail = f"无法找到 {resource}: {identifier}" if identifier else ""
        else:
            message = "资源不存在"
            detail = identifier
        super().__init__(404, message, detail)


class ValidationException(AppException):
    """业务校验失败异常 (422)

    当输入数据不符合业务规则（非格式问题）时抛出。
    例如：文件类型不支持、参数超出范围等。
    """

    def __init__(self, message: str):
        super().__init__(422, "数据校验失败", message)


class DuplicateException(AppException):
    """资源重复异常 (409)

    当尝试创建已存在的资源时抛出。
    例如：重复上传相同文档、注册已存在的用户名等。
    """

    def __init__(self, resource: str, field: str = ""):
        message = f"{resource}已存在"
        detail = f"{field} 的值重复" if field else ""
        super().__init__(409, message, detail)


class UnauthorizedException(AppException):
    """未认证异常 (401)

    当用户未登录或 Token 过期时抛出。
    """

    def __init__(self, message: str = "请先登录"):
        super().__init__(401, "未授权", message)


class ForbiddenException(AppException):
    """无权限异常 (403)

    当已认证用户尝试访问无权限的资源时抛出。
    """

    def __init__(self, message: str = "无权限执行此操作"):
        super().__init__(403, "无权限", message)


# ===== 服务端异常 (5xx) =====

class LLMException(AppException):
    """LLM 服务异常 (502)

    当调用 LLM API 失败时抛出。
    例如：API Key 无效、服务超时、返回异常等。
    """

    def __init__(self, message: str = "LLM 服务异常"):
        super().__init__(502, "LLM 服务异常", message)


class RetrievalException(AppException):
    """检索异常 (500)

    当向量数据库检索失败时抛出。
    """

    def __init__(self, message: str = "检索服务异常"):
        super().__init__(500, "检索服务异常", message)


class EmbeddingException(AppException):
    """Embedding 服务异常 (502)

    当调用 Embedding API 失败时抛出。
    """

    def __init__(self, message: str = "Embedding 服务异常"):
        super().__init__(502, "Embedding 服务异常", message)


class ProcessingException(AppException):
    """文档处理异常 (500)

    当文档解析、分块、向量化过程中发生不可恢复的错误时抛出。
    """

    def __init__(self, message: str = "文档处理失败"):
        super().__init__(500, "文档处理失败", message)
