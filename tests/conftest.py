import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def sample_problems() -> list[dict]:
    path = Path(__file__).parent / "fixtures" / "problems.json"
    return json.loads(path.read_text())


@pytest.fixture
def sample_clusters() -> list[dict]:
    path = Path(__file__).parent / "fixtures" / "clusters.json"
    return json.loads(path.read_text())


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.embed = AsyncMock(return_value=[[0.1] * 1536])
    return provider


@pytest.fixture
def mock_llm_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.is_spam = AsyncMock(return_value=(False, ""))
    provider.translate = AsyncMock(return_value=("English Title", "English description"))
    provider.generate_solution = AsyncMock(return_value="## Solution\n\nHere is a solution.")
    provider.generate_tags = AsyncMock(return_value=[{"label": "AI Governance", "level": 1}])
    return provider


@pytest.fixture
def mock_db_conn() -> MagicMock:
    """Provides a mock psycopg3 AsyncConnection.

    cursor() is a sync call returning an async context manager — matching
    the real psycopg3 AsyncConnection.cursor() behaviour used in BaseRepository._cursor().
    """
    conn = MagicMock()
    cursor = AsyncMock()
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=None)
    cursor.fetchall = AsyncMock(return_value=[])
    cursor.fetchone = AsyncMock(return_value=None)
    cursor.execute = AsyncMock(return_value=None)
    conn.cursor = MagicMock(return_value=cursor)
    return conn
