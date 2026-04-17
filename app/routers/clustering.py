import structlog
from fastapi import APIRouter, Depends

from app.dependencies import get_clustering_service, verify_webhook_secret
from app.models.responses import ClusteringResult
from app.services.clustering_service import ClusteringService

logger = structlog.get_logger()

router = APIRouter(prefix="/clustering", tags=["clustering"])


@router.post("/run", response_model=ClusteringResult, dependencies=[Depends(verify_webhook_secret)])
async def run_clustering(
    service: ClusteringService = Depends(get_clustering_service),
) -> ClusteringResult:
    """Trigger a full clustering run (admin operation).

    Fetches all approved problems with embeddings, runs HDBSCAN,
    and upserts clusters and problem assignments in the database.
    Also broadcasts cluster.updated events via WebSocket.

    Note: This is a synchronous (blocking) endpoint — use sparingly.
    The approval pipeline triggers clustering automatically in the background.
    """
    log = logger.bind(operation="manual_clustering_trigger")
    log.info("clustering_triggered_manually")

    result = await service.run_clustering()

    log.info(
        "clustering_done",
        clusters_updated=result.clusters_updated,
        problems_processed=result.problems_processed,
        duration_ms=result.duration_ms,
    )
    return result
