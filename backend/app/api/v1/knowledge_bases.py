"""
知识库 API 接口

路由：
    POST   /api/v1/knowledge-bases              — 创建知识库
    GET    /api/v1/knowledge-bases              — 知识库列表
    GET    /api/v1/knowledge-bases/{kb_id}      — 知识库详情
    PUT    /api/v1/knowledge-bases/{kb_id}      — 更新知识库
    DELETE /api/v1/knowledge-bases/{kb_id}      — 删除知识库
    POST   /api/v1/knowledge-bases/{kb_id}/members  — 添加成员
    DELETE /api/v1/knowledge-bases/{kb_id}/members/{user_id} — 移除成员
    GET    /api/v1/knowledge-bases/{kb_id}/members  — 成员列表
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user, get_kb_service
from app.models.database.user import User
from app.models.request_response.response import APIResponse, PageInfo, PaginatedData, PaginatedResponse
from app.services.kb_service import KBService
from pydantic import BaseModel, Field

router = APIRouter(prefix="/knowledge-bases", tags=["知识库"])


# ===== 请求模型 =====

class CreateKBRequest(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., min_length=1, max_length=255, description="知识库名称")
    description: str = Field("", max_length=500, description="描述")
    chunk_size: int = Field(500, ge=500, le=800, description="分块大小")
    chunk_overlap: int = Field(100, ge=50, le=200, description="重叠大小")
    embedding_model: str = Field("text-embedding-3-large", description="Embedding 模型")


class UpdateKBRequest(BaseModel):
    """更新知识库请求（所有字段可选）"""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=500)
    chunk_size: int | None = Field(None, ge=500, le=800)
    chunk_overlap: int | None = Field(None, ge=50, le=200)
    embedding_model: str | None = None


class AddMemberRequest(BaseModel):
    """添加成员请求"""
    user_id: str = Field(..., description="用户 ID")
    role: str = Field("viewer", pattern="^(admin|editor|viewer)$", description="角色")


# ===== 接口 =====

@router.post("", summary="创建知识库", status_code=201)
async def create_knowledge_base(
    req: CreateKBRequest,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[dict]:
    """创建新的知识库"""
    result = await kb_service.create(
        name=req.name,
        owner_id=current_user.id,
        description=req.description,
        chunk_size=req.chunk_size,
        chunk_overlap=req.chunk_overlap,
        embedding_model=req.embedding_model,
    )
    return APIResponse(code=201, message="知识库创建成功", data=result)


@router.get("", summary="获取知识库列表")
async def list_knowledge_bases(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: str | None = Query(None, description="按名称搜索"),
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> PaginatedResponse[dict]:
    """获取当前用户有权限的知识库列表"""
    items, total = await kb_service.list_by_user(
        user_id=current_user.id,
        page=page,
        page_size=page_size,
        search=search,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            page_info=PageInfo(total=total, page=page, page_size=page_size),
        )
    )


@router.get("/{kb_id}", summary="获取知识库详情")
async def get_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[dict]:
    """获取知识库详细信息（含统计和成员数）"""
    result = await kb_service.get_detail(UUID(kb_id), current_user.id)
    return APIResponse(data=result)


@router.put("/{kb_id}", summary="更新知识库")
async def update_knowledge_base(
    kb_id: str,
    req: UpdateKBRequest,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[dict]:
    """更新知识库配置（仅所有者可操作）"""
    update_data = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await kb_service.update(UUID(kb_id), current_user.id, **update_data)
    return APIResponse(message="知识库更新成功", data=result)


@router.delete("/{kb_id}", summary="删除知识库")
async def delete_knowledge_base(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[None]:
    """删除知识库（仅所有者可操作）"""
    await kb_service.delete(UUID(kb_id), current_user.id)
    return APIResponse(message="知识库已删除")


# ===== 成员管理 =====

@router.post("/{kb_id}/members", summary="添加成员")
async def add_member(
    kb_id: str,
    req: AddMemberRequest,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[dict]:
    """为知识库添加成员"""
    result = await kb_service.add_member(
        kb_id=UUID(kb_id),
        owner_id=current_user.id,
        user_id=UUID(req.user_id),
        role=req.role,
    )
    return APIResponse(message="成员添加成功", data=result)


@router.delete("/{kb_id}/members/{user_id}", summary="移除成员")
async def remove_member(
    kb_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[None]:
    """从知识库移除成员"""
    await kb_service.remove_member(
        kb_id=UUID(kb_id),
        owner_id=current_user.id,
        user_id=UUID(user_id),
    )
    return APIResponse(message="成员已移除")


@router.get("/{kb_id}/members", summary="获取成员列表")
async def list_members(
    kb_id: str,
    current_user: User = Depends(get_current_user),
    kb_service: KBService = Depends(get_kb_service),
) -> APIResponse[list[dict]]:
    """获取知识库成员列表"""
    members = await kb_service.list_members(UUID(kb_id), current_user.id)
    return APIResponse(data=members)
