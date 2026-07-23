"""
统一响应模型

项目所有 API 接口必须使用本模块定义的响应格式。

使用示例:
    from app.models.request_response.response import APIResponse

    @router.get("/users/{user_id}")
    async def get_user(user_id: str) -> APIResponse[UserData]:
        user = await service.get_user(user_id)
        return APIResponse(data=user)
"""

from typing import TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse[T](BaseModel):
    """统一 API 响应格式

    项目所有接口必须返回此模型的实例。

    Attributes:
        code: 状态码，200 表示成功
        message: 提示信息
        data: 响应数据（可为 None）
    """

    code: int = Field(200, description="状态码，200 表示成功")
    message: str = Field("success", description="提示信息")
    data: T | None = Field(None, description="响应数据")

    model_config = {"from_attributes": True}


class PageInfo(BaseModel):
    """分页信息"""

    total: int = Field(..., description="总记录数", ge=0)
    page: int = Field(..., description="当前页码", ge=1)
    page_size: int = Field(..., description="每页数量", ge=1, le=100)


class PaginatedData[T](BaseModel):
    """分页数据容器"""

    items: list[T] = Field(default_factory=list, description="数据列表")
    page_info: PageInfo = Field(..., description="分页信息")


class PaginatedResponse[T](APIResponse[PaginatedData[T]]):
    """分页响应格式

    用于列表类接口，包含分页信息。

    使用示例:
        return PaginatedResponse(
            data=PaginatedData(
                items=[...],
                page_info=PageInfo(total=100, page=1, page_size=20)
            )
        )
    """

    pass


class HealthCheckResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="healthy | unhealthy")
    version: str = Field(..., description="应用版本")
    checks: dict[str, bool] = Field(..., description="各服务连通状态")
    timestamp: str = Field(..., description="检查时间 (ISO 8601)")
