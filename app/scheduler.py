"""Clustering scheduler using APScheduler.

Runs ClusteringService.run_clustering() on a configurable interval.
Tracks last_run and exposes next_run for the health endpoint.
"""

from datetime import datetime, timezone

import psycopg
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.dependencies import get_llm_provider
from app.repositories.cluster_repository import ClusterRepository
from app.repositories.problem_repository import ProblemRepository
from app.repositories.tag_repository import TagRepository
from app.services.clustering_service import ClusteringService

logger = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None
last_clustering_run: datetime | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


def get_next_run() -> datetime | None:
    if _scheduler is None:
        return None
    jobs = _scheduler.get_jobs()
    if not jobs:
        return None
    return jobs[0].next_run_time


async def _run_clustering_job() -> None:
    """Scheduled job — creates its own service instances with fresh DB connections."""
    global last_clustering_run

    log = logger.bind(trigger="scheduler")
    log.info("scheduled_clustering_started")

    try:
        async with await psycopg.AsyncConnection.connect(settings.postgres_url) as conn:
            problem_repo = ProblemRepository(conn)
            cluster_repo = ClusterRepository(conn)
            tag_repo = TagRepository(conn)
            llm_provider = get_llm_provider()
            svc = ClusteringService(llm_provider, problem_repo, cluster_repo, tag_repo)
            result = await svc.run_clustering()

        last_clustering_run = datetime.now(tz=timezone.utc)
        log.info(
            "scheduled_clustering_complete",
            clusters_updated=result.clusters_updated,
            problems_processed=result.problems_processed,
            duration_ms=result.duration_ms,
        )
    except Exception:
        log.exception("scheduled_clustering_failed")


def start_scheduler(interval_minutes: int) -> AsyncIOScheduler:
    """Start the APScheduler with a clustering interval job.

    Args:
        interval_minutes: How often to run clustering (from settings.clustering_interval).

    Returns:
        The running scheduler instance.
    """
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _run_clustering_job,
        trigger="interval",
        minutes=interval_minutes,
        id="clustering",
        name="Periodic clustering run",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("scheduler_started", interval_minutes=interval_minutes)
    return _scheduler


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler_stopped")
    _scheduler = None
