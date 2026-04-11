from fastapi import APIRouter

from app.config import settings
from app.models.responses import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Service health check endpoint.

    Returns current status and configured provider names.
    Does not verify connectivity to external APIs or the database.
    """
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        embedding_provider=settings.embedding_provider,
        llm_provider=settings.llm_provider,
    )
