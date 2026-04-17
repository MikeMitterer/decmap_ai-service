import structlog
from fastapi import APIRouter, Depends, Request

from app.config import settings
from app.dependencies import get_similarity_service
from app.models.requests import SimilarityPayload
from app.models.responses import SimilarityResult
from app.rate_limit import limiter
from app.services.similarity_service import SimilarityService

logger = structlog.get_logger()

router = APIRouter(tags=["similarity"])


@router.post("/similarity", response_model=SimilarityResult)
@limiter.limit(settings.similarity_rate_limit)
async def check_similarity(
    request: Request,
    payload: SimilarityPayload,
    service: SimilarityService = Depends(get_similarity_service),
) -> SimilarityResult:
    """Find problems similar to the given text.

    Uses pgvector cosine similarity to search approved problems.
    Returns matching problems above the configured threshold and
    a flag indicating whether any are likely duplicates.

    No authentication required — called during problem submission.
    """
    log = logger.bind(text_length=len(payload.text))
    log.debug("similarity_request_received")

    result = await service.find_similar(payload.text)

    log.info(
        "similarity_request_complete",
        matches=len(result.similar_problems),
        has_duplicates=result.has_duplicates,
    )
    return result
