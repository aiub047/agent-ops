"""V1 API router – aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from app.api.v1.endpoints.agents import router as agents_router

router = APIRouter(prefix="/v1")
router.include_router(agents_router)

