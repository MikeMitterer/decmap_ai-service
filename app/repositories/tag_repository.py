from typing import Any

import structlog

from app.repositories.base import BaseRepository

logger = structlog.get_logger()


class TagRepository(BaseRepository):
    """Repository for the `tags` and `problem_tag` tables.

    Tags are hierarchical: L0 = root (system-managed), L1–L9 = AI-generated,
    L10 = user-assigned. This repository handles AI-generated L1 tags.
    """

    async def upsert_tag(self, label: str, level: int, parent_id: str | None = None) -> str:
        """Insert or return an existing tag by label and level.

        Args:
            label: Tag display name.
            level: Hierarchy level (1–9 for AI-generated tags).
            parent_id: Optional UUID of the parent tag.

        Returns:
            UUID of the upserted tag.
        """
        query = """
            INSERT INTO tags (label, level, parent_id)
            VALUES (%s, %s, %s)
            ON CONFLICT (label, level)
            DO UPDATE SET label = EXCLUDED.label
            RETURNING id::text
        """
        async with self._cursor() as cur:
            await cur.execute(query, (label, level, parent_id))
            row = await cur.fetchone()

        await self._conn.commit()
        tag_id: str = row["id"]
        logger.debug("tag_upserted", label=label, level=level, tag_id=tag_id)
        return tag_id

    async def assign_tag_to_cluster(self, cluster_id: str, tag_id: str) -> None:
        """Associate a tag with a cluster.

        Uses ON CONFLICT DO NOTHING to be idempotent.

        Args:
            cluster_id: UUID of the cluster.
            tag_id: UUID of the tag.
        """
        query = """
            INSERT INTO cluster_tag (cluster_id, tag_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """
        async with self._cursor() as cur:
            await cur.execute(query, (cluster_id, tag_id))
        await self._conn.commit()

    async def get_tags_for_cluster(self, cluster_id: str) -> list[dict[str, Any]]:
        """Fetch all tags associated with a cluster.

        Args:
            cluster_id: UUID of the cluster.

        Returns:
            List of tag dicts with keys: id, label, level.
        """
        query = """
            SELECT t.id::text, t.label, t.level
            FROM tags t
            JOIN cluster_tag ct ON ct.tag_id = t.id
            WHERE ct.cluster_id = %s
            ORDER BY t.level, t.label
        """
        async with self._cursor() as cur:
            await cur.execute(query, (cluster_id,))
            rows = await cur.fetchall()

        return list(rows)
