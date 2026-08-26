"""Bobby — Health Check Routes"""
from fastapi import APIRouter
from config.settings import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "bobby-api",
        "env": settings.app_env.value,
        "freshdesk_configured": bool(settings.freshdesk_api_key),
        "llm_configured": bool(settings.llm_api_key),
    }
