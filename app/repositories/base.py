import psycopg
from psycopg.rows import dict_row


class BaseRepository:
    """Base class for all repositories.

    Holds a shared async connection and provides helper utilities.
    All subclasses use raw SQL via psycopg3 — no ORM.
    """

    def __init__(self, conn: psycopg.AsyncConnection) -> None:  # type: ignore[type-arg]
        self._conn = conn

    def _cursor(self) -> psycopg.AsyncCursor:  # type: ignore[type-arg]
        """Return a dict_row cursor for the shared connection."""
        return self._conn.cursor(row_factory=dict_row)
