"""FastAPI dependency injection wiring.

Providers and repositories are created once per request via Depends().
The DB connection is acquired from a connection pool opened at startup.

Usage:
    @router.post("/example")
    async def example(service: SimilarityService = Depends(get_similarity_service)):
        ...
"""

from typing import AsyncGenerator

import psycopg
import structlog
from fastapi import Depends, Header, HTTPException, status

from app.config import settings
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.factory import create_embedding_provider
from app.providers.llm.base import LLMProvider
from app.providers.llm.factory import create_llm_provider
from app.repositories.cluster_repository import ClusterRepository
from app.repositories.problem_repository import ProblemRepository
from app.repositories.tag_repository import TagRepository
from app.services.clustering_service import ClusteringService
from app.services.similarity_service import SimilarityService
from app.services.solution_service import SolutionService
from app.services.spam_filter_service import SpamFilterService
from app.services.translation_service import TranslationService

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Module-level provider singletons (created once at startup)
# ---------------------------------------------------------------------------
_embedding_provider: EmbeddingProvider | None = None
_llm_provider: LLMProvider | None = None


def init_providers() -> None:
    """Initialise provider singletons. Call from application lifespan."""
    global _embedding_provider, _llm_provider
    _embedding_provider = create_embedding_provider(settings)
    _llm_provider = create_llm_provider(settings)
    logger.info(
        "providers_initialised",
        embedding=settings.embedding_provider,
        llm=settings.llm_provider,
    )


def get_embedding_provider() -> EmbeddingProvider:
    assert _embedding_provider is not None, "Providers not initialised"
    return _embedding_provider


def get_llm_provider() -> LLMProvider:
    assert _llm_provider is not None, "Providers not initialised"
    return _llm_provider


# ---------------------------------------------------------------------------
# Webhook authentication
# ---------------------------------------------------------------------------


def verify_webhook_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
    """Validate the shared secret sent by Directus Flows.

    If WEBHOOK_SECRET is not configured, validation is skipped (dev mode).
    In production, always set WEBHOOK_SECRET.
    """
    if not settings.webhook_secret:
        return
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing webhook secret",
        )


# ---------------------------------------------------------------------------
# Per-request DB connection
# ---------------------------------------------------------------------------


async def get_db_conn() -> AsyncGenerator[psycopg.AsyncConnection, None]:  # type: ignore[type-arg]
    """Yield a fresh async psycopg3 connection per request."""
    async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
        yield conn


# ---------------------------------------------------------------------------
# Repository dependencies
# ---------------------------------------------------------------------------


def get_problem_repo(
    conn: psycopg.AsyncConnection = Depends(get_db_conn),  # type: ignore[type-arg]
) -> ProblemRepository:
    return ProblemRepository(conn)


def get_cluster_repo(
    conn: psycopg.AsyncConnection = Depends(get_db_conn),  # type: ignore[type-arg]
) -> ClusterRepository:
    return ClusterRepository(conn)


def get_tag_repo(
    conn: psycopg.AsyncConnection = Depends(get_db_conn),  # type: ignore[type-arg]
) -> TagRepository:
    return TagRepository(conn)


# ---------------------------------------------------------------------------
# Service dependencies
# ---------------------------------------------------------------------------


def get_similarity_service(
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    problem_repo: ProblemRepository = Depends(get_problem_repo),
) -> SimilarityService:
    return SimilarityService(embedding_provider, problem_repo)


def get_spam_filter_service(
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> SpamFilterService:
    return SpamFilterService(llm_provider)


def get_translation_service(
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> TranslationService:
    return TranslationService(llm_provider)


def get_solution_service(
    llm_provider: LLMProvider = Depends(get_llm_provider),
    problem_repo: ProblemRepository = Depends(get_problem_repo),
) -> SolutionService:
    return SolutionService(llm_provider, problem_repo)


def get_clustering_service(
    llm_provider: LLMProvider = Depends(get_llm_provider),
    problem_repo: ProblemRepository = Depends(get_problem_repo),
    cluster_repo: ClusterRepository = Depends(get_cluster_repo),
    tag_repo: TagRepository = Depends(get_tag_repo),
) -> ClusteringService:
    return ClusteringService(llm_provider, problem_repo, cluster_repo, tag_repo)
