"""Unit tests for the clustering scheduler."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.scheduler as scheduler_module
from app.scheduler import get_next_run, start_scheduler, stop_scheduler


@pytest.fixture(autouse=True)
async def reset_scheduler():
    """Ensure scheduler state is clean before and after each test."""
    scheduler_module._scheduler = None
    scheduler_module.last_clustering_run = None
    yield
    stop_scheduler()
    scheduler_module.last_clustering_run = None


# ---------------------------------------------------------------------------
# start / stop / query — must be async because AsyncIOScheduler.start()
# requires a running event loop
# ---------------------------------------------------------------------------


async def test_start_scheduler_creates_running_scheduler() -> None:
    """start_scheduler returns a running AsyncIOScheduler."""
    sched = start_scheduler(interval_minutes=60)
    assert sched is not None
    assert sched.running


async def test_start_scheduler_registers_clustering_job() -> None:
    """The scheduler has exactly one job with id 'clustering'."""
    sched = start_scheduler(interval_minutes=60)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    assert jobs[0].id == "clustering"


def test_get_next_run_returns_none_before_start() -> None:
    """get_next_run returns None when scheduler has not been started."""
    assert get_next_run() is None


async def test_get_next_run_returns_datetime_after_start() -> None:
    """get_next_run returns a datetime once the scheduler is running."""
    start_scheduler(interval_minutes=60)
    next_run = get_next_run()
    assert isinstance(next_run, datetime)


async def test_stop_scheduler_stops_running_scheduler() -> None:
    """stop_scheduler shuts down the scheduler and clears the singleton."""
    start_scheduler(interval_minutes=60)
    stop_scheduler()
    assert scheduler_module._scheduler is None


def test_last_clustering_run_is_none_initially() -> None:
    """last_clustering_run starts as None before any job executes."""
    assert scheduler_module.last_clustering_run is None


# ---------------------------------------------------------------------------
# _run_clustering_job
# ---------------------------------------------------------------------------


async def test_run_clustering_job_updates_last_run() -> None:
    """_run_clustering_job sets last_clustering_run after a successful run."""
    mock_result = MagicMock(clusters_updated=1, problems_processed=3, duration_ms=100)

    mock_conn = AsyncMock()
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    mock_svc = AsyncMock()
    mock_svc.run_clustering = AsyncMock(return_value=mock_result)

    with (
        patch("app.scheduler.psycopg") as mock_psycopg,
        patch("app.scheduler.get_llm_provider"),
        patch("app.scheduler.ClusteringService", return_value=mock_svc),
        patch("app.scheduler.ProblemRepository"),
        patch("app.scheduler.ClusterRepository"),
        patch("app.scheduler.TagRepository"),
        patch("app.scheduler.settings"),
    ):
        mock_psycopg.AsyncConnection.connect = AsyncMock(return_value=mock_conn)
        await scheduler_module._run_clustering_job()

    assert scheduler_module.last_clustering_run is not None
    assert isinstance(scheduler_module.last_clustering_run, datetime)
    assert scheduler_module.last_clustering_run.tzinfo == timezone.utc
