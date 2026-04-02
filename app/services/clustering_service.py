import ast
import time

import hdbscan
import numpy as np
import structlog

from app.models.events import ClusterUpdatedEvent, ClusterUpdatedPayload
from app.models.responses import ClusteringResult
from app.providers.llm.base import LLMProvider
from app.repositories.cluster_repository import ClusterRepository
from app.repositories.problem_repository import ProblemRepository
from app.services import websocket_service

logger = structlog.get_logger()


def _parse_embedding(raw: str) -> list[float]:
    """Parse a pgvector embedding string (e.g. '[0.1,0.2,...]') into a float list."""
    # pgvector returns vectors as a string like '[0.1,0.2,...]'
    cleaned = raw.strip()
    if cleaned.startswith("["):
        try:
            return ast.literal_eval(cleaned)
        except (ValueError, SyntaxError):
            pass
    # Fallback: strip brackets and split
    return [float(x) for x in cleaned.strip("[]").split(",")]


class ClusteringService:
    """Clusters approved problems using HDBSCAN on their embeddings.

    Algorithm:
    1. Fetch all approved problems that have embeddings.
    2. Run HDBSCAN(min_cluster_size=3, metric='cosine').
    3. For each discovered cluster (ignoring noise label -1):
       a. Compute centroid (mean of member embeddings).
       b. Ask LLM to generate a descriptive label.
       c. Upsert the cluster in the database.
       d. Update problem_cluster junction table.
       e. Broadcast cluster.updated WebSocket event.
    4. Return ClusteringResult with summary statistics.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        problem_repo: ProblemRepository,
        cluster_repo: ClusterRepository,
    ) -> None:
        self._llm_provider = llm_provider
        self._problem_repo = problem_repo
        self._cluster_repo = cluster_repo

    async def run_clustering(self) -> ClusteringResult:
        """Execute the full clustering pipeline.

        Returns:
            ClusteringResult with counts and duration.
        """
        start_ms = time.monotonic()
        log = logger.bind(operation="clustering")

        # 1. Fetch problems with embeddings
        problems = await self._problem_repo.get_approved_with_embeddings()
        log.info("clustering_started", problem_count=len(problems))

        if len(problems) < 3:
            log.info("clustering_skipped_insufficient_data", count=len(problems))
            elapsed = int((time.monotonic() - start_ms) * 1000)
            return ClusteringResult(
                clusters_updated=0,
                problems_processed=len(problems),
                duration_ms=elapsed,
            )

        # Parse embeddings from pgvector string format
        embeddings_list: list[list[float]] = [
            _parse_embedding(p["embedding_raw"]) for p in problems
        ]
        embeddings_array = np.array(embeddings_list, dtype=np.float32)

        # 2. Run HDBSCAN
        clusterer = hdbscan.HDBSCAN(min_cluster_size=3, metric="cosine")
        labels: np.ndarray = clusterer.fit_predict(embeddings_array)
        probabilities: np.ndarray = getattr(
            clusterer, "probabilities_", np.ones(len(labels))
        )

        unique_labels = set(int(label) for label in labels if int(label) != -1)
        log.info("hdbscan_complete", cluster_count=len(unique_labels))

        clusters_updated = 0

        # 3. Process each cluster
        for cluster_label in unique_labels:
            member_indices = [
                i for i, label in enumerate(labels) if int(label) == cluster_label
            ]
            member_problems = [problems[i] for i in member_indices]
            member_embeddings = embeddings_array[member_indices]

            # a. Compute centroid
            centroid: list[float] = np.mean(member_embeddings, axis=0).tolist()

            # b. Generate cluster label via LLM
            tags = await self._llm_provider.generate_tags(member_problems)
            cluster_name = tags[0]["label"] if tags else f"Cluster {cluster_label}"

            # c. Upsert cluster in DB
            db_cluster_id = await self._cluster_repo.upsert_cluster(
                label=cluster_name,
                centroid=centroid,
            )

            # d. Update problem_cluster junction table
            for i, problem in enumerate(member_problems):
                weight = float(probabilities[member_indices[i]])
                await self._cluster_repo.assign_problem_to_cluster(
                    problem_id=problem["id"],
                    cluster_id=db_cluster_id,
                    weight=weight,
                )

            # e. Broadcast WebSocket event
            event = ClusterUpdatedEvent(
                payload=ClusterUpdatedPayload(
                    id=db_cluster_id,
                    label=cluster_name,
                    problem_count=len(member_problems),
                )
            )
            await websocket_service.broadcast(event)

            clusters_updated += 1
            log.debug(
                "cluster_processed",
                cluster_id=db_cluster_id,
                label=cluster_name,
                members=len(member_problems),
            )

        elapsed = int((time.monotonic() - start_ms) * 1000)
        log.info(
            "clustering_complete",
            clusters_updated=clusters_updated,
            problems_processed=len(problems),
            duration_ms=elapsed,
        )

        return ClusteringResult(
            clusters_updated=clusters_updated,
            problems_processed=len(problems),
            duration_ms=elapsed,
        )
