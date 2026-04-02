from unittest.mock import AsyncMock, patch

import pytest

from app.models.responses import SimilarProblem, SimilarityResult
from app.services.similarity_service import SimilarityService


@pytest.fixture
def problem_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.find_similar = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def similarity_service(mock_embedding_provider, problem_repo) -> SimilarityService:
    return SimilarityService(mock_embedding_provider, problem_repo)


async def test_find_similar_generates_embedding(
    similarity_service, mock_embedding_provider, problem_repo
) -> None:
    """Embedding is generated for the input text."""
    await similarity_service.find_similar("AI governance problem in our company")

    mock_embedding_provider.embed.assert_awaited_once_with(
        ["AI governance problem in our company"]
    )


async def test_find_similar_calls_pgvector_query(
    similarity_service, mock_embedding_provider, problem_repo
) -> None:
    """The embedding is passed to the repository for pgvector lookup."""
    expected_embedding = [0.1] * 1536
    mock_embedding_provider.embed.return_value = [expected_embedding]

    with patch("app.services.similarity_service.settings") as mock_settings:
        mock_settings.similarity_threshold = 0.85
        mock_settings.duplicate_threshold = 0.92
        service = SimilarityService(mock_embedding_provider, problem_repo)
        await service.find_similar("test query")

    problem_repo.find_similar.assert_awaited_once_with(expected_embedding, 0.85)


async def test_find_similar_returns_filtered_results(
    mock_embedding_provider, problem_repo
) -> None:
    """Results from the repository are passed through to SimilarityResult."""
    problem_repo.find_similar.return_value = [
        SimilarProblem(id="prob-001", title="AI Governance", score=0.91),
        SimilarProblem(id="prob-002", title="Data Quality", score=0.88),
    ]

    with patch("app.services.similarity_service.settings") as mock_settings:
        mock_settings.similarity_threshold = 0.85
        mock_settings.duplicate_threshold = 0.92
        service = SimilarityService(mock_embedding_provider, problem_repo)
        result = await service.find_similar("test")

    assert len(result.similar_problems) == 2
    assert result.similar_problems[0].id == "prob-001"
    assert result.similar_problems[1].id == "prob-002"


async def test_has_duplicates_false_when_no_score_exceeds_threshold(
    mock_embedding_provider, problem_repo
) -> None:
    """has_duplicates is False when all scores are below duplicate_threshold."""
    problem_repo.find_similar.return_value = [
        SimilarProblem(id="prob-001", title="AI Governance", score=0.88),
        SimilarProblem(id="prob-002", title="Data Quality", score=0.87),
    ]

    with patch("app.services.similarity_service.settings") as mock_settings:
        mock_settings.similarity_threshold = 0.85
        mock_settings.duplicate_threshold = 0.92
        service = SimilarityService(mock_embedding_provider, problem_repo)
        result = await service.find_similar("test")

    assert result.has_duplicates is False


async def test_has_duplicates_true_when_score_exceeds_threshold(
    mock_embedding_provider, problem_repo
) -> None:
    """has_duplicates is True when at least one score exceeds duplicate_threshold."""
    problem_repo.find_similar.return_value = [
        SimilarProblem(id="prob-001", title="AI Governance", score=0.95),
    ]

    with patch("app.services.similarity_service.settings") as mock_settings:
        mock_settings.similarity_threshold = 0.85
        mock_settings.duplicate_threshold = 0.92
        service = SimilarityService(mock_embedding_provider, problem_repo)
        result = await service.find_similar("test")

    assert result.has_duplicates is True


async def test_find_similar_empty_results(
    mock_embedding_provider, problem_repo
) -> None:
    """Empty result set returns SimilarityResult with empty list and no duplicates."""
    problem_repo.find_similar.return_value = []

    with patch("app.services.similarity_service.settings") as mock_settings:
        mock_settings.similarity_threshold = 0.85
        mock_settings.duplicate_threshold = 0.92
        service = SimilarityService(mock_embedding_provider, problem_repo)
        result = await service.find_similar("completely unique problem")

    assert result.similar_problems == []
    assert result.has_duplicates is False
