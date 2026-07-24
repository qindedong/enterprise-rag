"""
API v1 路由汇总
"""

from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as doc_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.knowledge_bases import router as kb_router
from app.api.v1.rag import router as rag_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(kb_router)
api_router.include_router(doc_router)
api_router.include_router(rag_router)
api_router.include_router(feedback_router)
api_router.include_router(analytics_router)
api_router.include_router(api_keys_router)
