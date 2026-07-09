"""
API v1 路由汇总

将各模块路由注册到统一的 API Router.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.knowledge_bases import router as kb_router
from app.api.v1.documents import router as doc_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(kb_router)
api_router.include_router(doc_router)

# 后续 Sprint 将注册:
# from app.api.v1.documents import router as doc_router
# api_router.include_router(doc_router)
# from app.api.v1.rag import router as rag_router
# api_router.include_router(rag_router)
# from app.api.v1.conversations import router as conv_router
# api_router.include_router(conv_router)
