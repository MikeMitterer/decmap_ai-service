from enum import StrEnum

import psycopg
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from app.config import settings
from app.dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_spam_filter_service,
)
from app.models.events import (
    ProblemApprovedEvent,
    ProblemApprovedPayload,
    ProblemRejectedEvent,
    ProblemRejectedPayload,
    SolutionApprovedEvent,
    SolutionApprovedPayload,
    VoteChangedEvent,
    VoteChangedPayload,
)
from app.models.requests import (
    ProblemApprovedPayload as ProblemApprovedRequest,
)
from app.models.requests import (
    ProblemSubmittedPayload,
    SolutionApprovedPayload as SolutionApprovedRequest,
    VoteChangedPayload as VoteChangedRequest,
)
from app.providers.embedding.base import EmbeddingProvider
from app.providers.llm.base import LLMProvider
from app.repositories.cluster_repository import ClusterRepository
from app.repositories.problem_repository import ProblemRepository
from app.services import websocket_service
from app.services.clustering_service import ClusteringService
from app.services.solution_service import SolutionService
from app.services.spam_filter_service import SpamFilterService

logger = structlog.get_logger()

router = APIRouter(prefix="/hooks", tags=["hooks"])


class ProblemStatus(StrEnum):
    PENDING = "pending"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


def _verify_webhook_secret(x_webhook_secret: str | None = Header(default=None)) -> None:
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


@router.post(
    "/problem-submitted",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_verify_webhook_secret)],
)
async def problem_submitted(
    payload: ProblemSubmittedPayload,
    background_tasks: BackgroundTasks,
    spam_service: SpamFilterService = Depends(get_spam_filter_service),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> dict:
    """Directus Flow webhook — called when a new problem is submitted.

    Pipeline:
    1. Run spam/bot filter (honeypot → signals → LLM).
    2. Update problem status in DB accordingly.
    3. If not rejected, schedule embedding generation in background.

    The problem enters either 'pending', 'needs_review', or 'rejected' state.

    Note: The DB write for status and the background embedding task each open
    their own short-lived connections so the request-scoped connection lifetime
    does not affect background work.
    """
    log = logger.bind(problem_id=payload.problem_id)
    log.info("problem_submitted_hook_received")

    combined_text = f"{payload.title}\n\n{payload.description}"
    filter_result = await spam_service.evaluate(
        text=combined_text,
        signals=payload.signals,
        honeypot=payload.honeypot,
    )

    # Write status to DB — own connection, not request-scoped
    async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
        repo = ProblemRepository(conn)
        await repo.update_status(payload.problem_id, filter_result.status)

    if filter_result.status == ProblemStatus.REJECTED:
        log.info("problem_rejected", reason=filter_result.reason)
        await websocket_service.broadcast(
            ProblemRejectedEvent(
                payload=ProblemRejectedPayload(
                    id=payload.problem_id,
                    reason=filter_result.reason or "spam",
                )
            )
        )
        return {"status": filter_result.status, "reason": filter_result.reason}

    # Capture immutable values for the background closure
    problem_id = payload.problem_id
    text_snapshot = combined_text

    async def generate_embedding() -> None:
        """Background task — opens its own DB connection independent of the request."""
        try:
            embeddings = await embedding_provider.embed([text_snapshot])
            async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
                repo = ProblemRepository(conn)
                await repo.update_embedding(problem_id, embeddings[0])
            log.info("embedding_generated_on_submit", problem_id=problem_id)
        except Exception as exc:
            log.error("embedding_generation_failed", problem_id=problem_id, error=str(exc))

    background_tasks.add_task(generate_embedding)

    log.info("problem_queued", status=filter_result.status)
    return {"status": filter_result.status}


@router.post(
    "/problem-approved",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_verify_webhook_secret)],
)
async def problem_approved(
    payload: ProblemApprovedRequest,
    background_tasks: BackgroundTasks,
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> dict:
    """Directus Flow webhook — called when a moderator approves a problem.

    Pipeline (all run in background after immediate response):
    1. Generate and store embedding for the problem text.
    2. Generate AI solution approach and store it.
    3. Trigger full re-clustering.
    4. Broadcast problem.approved WebSocket event.
    """
    log = logger.bind(problem_id=payload.problem_id)
    log.info("problem_approved_hook_received")

    # Fetch problem synchronously before returning — providers are stateless singletons
    async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
        repo = ProblemRepository(conn)
        problem = await repo.get_by_id(payload.problem_id)

    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Problem {payload.problem_id} not found",
        )

    # Capture immutable values; providers are module-level singletons (safe to close over)
    problem_id = payload.problem_id
    problem_snapshot = dict(problem)

    async def run_approval_pipeline() -> None:
        """Background task — each DB operation opens its own connection."""
        try:
            description = problem_snapshot.get("description_en") or problem_snapshot.get("description", "")
            combined_text = f"{problem_snapshot['title']}\n\n{description}"

            # 1. Generate and store embedding
            embeddings = await embedding_provider.embed([combined_text])
            async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
                repo = ProblemRepository(conn)
                await repo.update_embedding(problem_id, embeddings[0])
            log.info("embedding_stored_on_approval")

            # 2. Generate AI solution
            solution_content = await llm_provider.generate_solution(
                problem_snapshot["title"], description
            )
            async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
                repo = ProblemRepository(conn)
                await repo.create_solution(problem_id, solution_content, is_ai_generated=True)
            log.info("ai_solution_generated")

            # 3. Trigger clustering
            async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
                problem_repo = ProblemRepository(conn)
                cluster_repo = ClusterRepository(conn)
                clustering_svc = ClusteringService(llm_provider, problem_repo, cluster_repo)
                await clustering_svc.run_clustering()

            # 4. Broadcast approval event
            await websocket_service.broadcast(
                ProblemApprovedEvent(
                    payload=ProblemApprovedPayload(id=problem_id)
                )
            )
            log.info("approval_pipeline_complete")
        except Exception as exc:
            log.error("approval_pipeline_failed", error=str(exc))

    background_tasks.add_task(run_approval_pipeline)
    return {"status": "processing"}


@router.post(
    "/solution-approved",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_verify_webhook_secret)],
)
async def solution_approved(
    payload: SolutionApprovedRequest,
) -> dict:
    """Directus Flow webhook — called when a solution approach is approved."""
    log = logger.bind(solution_id=payload.solution_id, problem_id=payload.problem_id)
    log.info("solution_approved_hook_received")

    await websocket_service.broadcast(
        SolutionApprovedEvent(
            payload=SolutionApprovedPayload(
                id=payload.solution_id,
                problem_id=payload.problem_id,
                is_ai_generated=False,
            )
        )
    )

    return {"status": "broadcast_sent"}


@router.post(
    "/vote-changed",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(_verify_webhook_secret)],
)
async def vote_changed(
    payload: VoteChangedRequest,
) -> dict:
    """Directus Flow webhook — called when a vote is cast or changed.

    The Directus Flow only needs to send entity_id and entity_type.
    new_score is calculated from the DB if not provided in the payload,
    so the Flow does not need to compute the score itself.
    """
    log = logger.bind(entity_id=payload.entity_id, entity_type=payload.entity_type)
    log.debug("vote_changed_hook_received")

    if payload.new_score is not None:
        new_score = payload.new_score
    else:
        table = "problems" if payload.entity_type == "problem" else "solution_approaches"
        async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"SELECT vote_score FROM {table} WHERE id = %s",  # noqa: S608
                    (payload.entity_id,),
                )
                row = await cur.fetchone()
        new_score = row[0] if row else 0
        log.debug("vote_score_fetched_from_db", new_score=new_score)

    await websocket_service.broadcast(
        VoteChangedEvent(
            payload=VoteChangedPayload(
                entity_id=payload.entity_id,
                entity_type=payload.entity_type,
                new_score=new_score,
            )
        )
    )

    return {"status": "broadcast_sent"}
