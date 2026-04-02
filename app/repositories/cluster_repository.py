from typing import Any

import structlog

from app.repositories.base import BaseRepository

logger = structlog.get_logger()


class ClusterRepository(BaseRepository):
    """Repository for the `clusters` and `problem_cluster` tables."""

    async def upsert_cluster(
        self,
        label: str,
        centroid: list[float],
    ) -> str:
        """Insert a new cluster or update an existing one by label.

        Args:
            label: Human-readable cluster label (from LLM).
            centroid: Mean embedding vector for the cluster.

        Returns:
            UUID of the upserted cluster.
        """
        query = """
            INSERT INTO clusters (label, centroid)
            VALUES (%s, %s::vector)
            ON CONFLICT (label)
            DO UPDATE SET
                centroid = EXCLUDED.centroid,
                updated_at = now()
            RETURNING id::text
        """
        async with self._cursor() as cur:
            await cur.execute(query, (label, centroid))
            row = await cur.fetchone()

        await self._conn.commit()
        cluster_id: str = row["id"]
        logger.debug("cluster_upserted", label=label, cluster_id=cluster_id)
        return cluster_id

    async def assign_problem_to_cluster(
        self, problem_id: str, cluster_id: str, weight: float
    ) -> None:
        """Insert or update a problem→cluster assignment in the junction table.

        Args:
            problem_id: UUID of the problem.
            cluster_id: UUID of the cluster.
            weight: HDBSCAN membership probability (0.0 – 1.0).
        """
        query = """
            INSERT INTO problem_cluster (problem_id, cluster_id, weight)
            VALUES (%s, %s, %s)
            ON CONFLICT (problem_id, cluster_id)
            DO UPDATE SET weight = EXCLUDED.weight
        """
        async with self._cursor() as cur:
            await cur.execute(query, (problem_id, cluster_id, weight))
        await self._conn.commit()

    async def get_all(self) -> list[dict[str, Any]]:
        """Fetch all clusters with their problem counts.

        Returns:
            List of cluster dicts with keys: id, label, problem_count.
        """
        query = """
            SELECT
                c.id::text,
                c.label,
                COUNT(pc.problem_id) AS problem_count
            FROM clusters c
            LEFT JOIN problem_cluster pc ON pc.cluster_id = c.id
            GROUP BY c.id, c.label
            ORDER BY problem_count DESC
        """
        async with self._cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()

        return list(rows)
