"""Add pgvector extension and embedding columns

Revision ID: 001
Revises:
Create Date: 2026-04-02

Notes:
    - The `problems` and `solution_approaches` tables are managed by Directus.
    - This migration ONLY adds the pgvector extension and the `embedding` column
      to those tables. It never touches other columns.
    - Safe to run multiple times (all statements use IF NOT EXISTS / IF EXISTS).
    - Index type: ivfflat (approximate nearest-neighbor, good for >= 1M vectors).
      Use hnsw for smaller datasets if preferred.
"""

from alembic import op

# revision identifiers
revision = "001"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1536  # OpenAI text-embedding-3-small


def upgrade() -> None:
    # 1. Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. Add embedding column to problems (managed by Directus — only adding column)
    op.execute(
        f"ALTER TABLE problems "
        f"ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})"
    )

    # 3. Add embedding column to solution_approaches
    op.execute(
        f"ALTER TABLE solution_approaches "
        f"ADD COLUMN IF NOT EXISTS embedding vector({EMBEDDING_DIM})"
    )

    # 4. ivfflat index on problems.embedding (cosine distance)
    #    Partial index — only index rows that have embeddings (avoids NULL overhead)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_problems_embedding_ivfflat
        ON problems
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding IS NOT NULL
        """
    )

    # 5. ivfflat index on solution_approaches.embedding (cosine distance)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_solution_approaches_embedding_ivfflat
        ON solution_approaches
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_solution_approaches_embedding_ivfflat")
    op.execute("DROP INDEX IF EXISTS ix_problems_embedding_ivfflat")
    op.execute("ALTER TABLE solution_approaches DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE problems DROP COLUMN IF EXISTS embedding")
    # Note: We intentionally do NOT drop the vector extension on downgrade
    # as other parts of the system may depend on it.
