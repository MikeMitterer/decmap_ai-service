from typing import Any

import structlog

from app.models.responses import SimilarProblem
from app.repositories.base import BaseRepository

logger = structlog.get_logger()


class ProblemRepository(BaseRepository):
    """Repository for the `problems` and `solution_approaches` tables.

    The `problems` table is managed by Directus. This repository only
    reads/updates AI-specific columns (embedding, status) and inserts
    AI-generated solution approaches.
    """

    async def find_similar(
        self, embedding: list[float], threshold: float
    ) -> list[SimilarProblem]:
        """Find approved problems similar to the given embedding using pgvector.

        Uses cosine distance operator (<=>). Only returns approved, non-deleted problems.
        Results are ordered by similarity (highest first).

        Args:
            embedding: Query vector (1536 dims).
            threshold: Minimum cosine similarity score (0.0 – 1.0).

        Returns:
            List of SimilarProblem sorted by descending score.
        """
        log = logger.bind(threshold=threshold)
        query = """
            SELECT
                id::text,
                title,
                1 - (embedding <=> %s::vector) AS score
            FROM problems
            WHERE
                status = 'approved'
                AND embedding IS NOT NULL
                AND deleted_at IS NULL
                AND 1 - (embedding <=> %s::vector) >= %s
            ORDER BY score DESC
            LIMIT 10
        """
        async with self._cursor() as cur:
            await cur.execute(query, (embedding, embedding, threshold))
            rows = await cur.fetchall()

        results = [
            SimilarProblem(id=row["id"], title=row["title"], score=float(row["score"]))
            for row in rows
        ]
        log.debug("similar_problems_found", count=len(results))
        return results

    async def update_embedding(self, problem_id: str, embedding: list[float]) -> None:
        """Persist the computed embedding vector for a problem.

        Args:
            problem_id: UUID of the problem to update.
            embedding: Vector to store (must match configured dimensions).
        """
        async with self._cursor() as cur:
            await cur.execute(
                "UPDATE problems SET embedding = %s::vector WHERE id = %s",
                (embedding, problem_id),
            )
        await self._conn.commit()
        logger.debug("embedding_updated", problem_id=problem_id)

    async def update_status(self, problem_id: str, status: str) -> None:
        """Update the moderation status of a problem.

        Args:
            problem_id: UUID of the problem.
            status: New status string (see ProblemStatus enum).
        """
        async with self._cursor() as cur:
            await cur.execute(
                "UPDATE problems SET status = %s WHERE id = %s",
                (status, problem_id),
            )
        await self._conn.commit()
        logger.debug("status_updated", problem_id=problem_id, status=status)

    async def get_approved_with_embeddings(self) -> list[dict[str, Any]]:
        """Fetch all approved problems that have embeddings computed.

        Used by the clustering service. Returns full problem data
        including the embedding vector for HDBSCAN.

        Returns:
            List of dicts with keys: id, title, description_en, embedding.
        """
        query = """
            SELECT
                id::text,
                title,
                description_en,
                embedding::text AS embedding_raw
            FROM problems
            WHERE
                status = 'approved'
                AND embedding IS NOT NULL
                AND deleted_at IS NULL
            ORDER BY created_at ASC
        """
        async with self._cursor() as cur:
            await cur.execute(query)
            rows = await cur.fetchall()

        logger.debug("approved_problems_fetched", count=len(rows))
        return list(rows)

    async def get_by_id(self, problem_id: str) -> dict[str, Any] | None:
        """Fetch a single problem by ID.

        Args:
            problem_id: UUID of the problem.

        Returns:
            Problem dict or None if not found / soft-deleted.
        """
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT id::text, title, description, description_en, status
                FROM problems
                WHERE id = %s AND deleted_at IS NULL
                """,
                (problem_id,),
            )
            return await cur.fetchone()

    async def create_solution(self, problem_id: str, content: str) -> str:
        """Insert an AI-generated solution approach for a problem.

        Sets is_ai_generated=true and status='approved' immediately.

        Args:
            problem_id: UUID of the parent problem.
            content: Markdown-formatted solution text.

        Returns:
            UUID of the newly created solution approach.
        """
        query = """
            INSERT INTO solution_approaches
                (problem_id, content, is_ai_generated, status)
            VALUES (%s, %s, true, 'approved')
            RETURNING id::text
        """
        async with self._cursor() as cur:
            await cur.execute(query, (problem_id, content))
            row = await cur.fetchone()

        await self._conn.commit()
        solution_id: str = row["id"]
        logger.info("ai_solution_created", problem_id=problem_id, solution_id=solution_id)
        return solution_id
