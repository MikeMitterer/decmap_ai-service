from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.models.responses import ClusteringResult
from app.services.clustering_service import ClusteringService, _parse_embedding


# ---------------------------------------------------------------------------
# Unit tests for _parse_embedding helper
# ---------------------------------------------------------------------------


def test_parse_embedding_standard_format() -> None:
    """Parses pgvector string format '[0.1,0.2,0.3]'."""
    result = _parse_embedding("[0.1,0.2,0.3]")
    assert result == pytest.approx([0.1, 0.2, 0.3])


def test_parse_embedding_with_spaces() -> None:
    """Handles spaces around brackets."""
    result = _parse_embedding(" [0.5, 0.6] ")
    assert result == pytest.approx([0.5, 0.6])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cluster_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.upsert_cluster = AsyncMock(return_value="cluster-uuid-001")
    repo.assign_problem_to_cluster = AsyncMock()
    return repo


@pytest.fixture
def tag_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.upsert_tag = AsyncMock(return_value="tag-uuid-001")
    repo.assign_tag_to_cluster = AsyncMock()
    return repo


@pytest.fixture
def problem_repo_with_problems() -> AsyncMock:
    """Returns 3 approved problems with embeddings."""
    repo = AsyncMock()
    repo.get_approved_with_embeddings = AsyncMock(
        return_value=[
            {
                "id": "prob-001",
                "title": "AI Governance",
                "description_en": "Missing AI governance framework",
                "embedding_raw": "[" + ",".join(["0.1"] * 1536) + "]",
            },
            {
                "id": "prob-002",
                "title": "Data Quality",
                "description_en": "Poor data quality for AI",
                "embedding_raw": "[" + ",".join(["0.2"] * 1536) + "]",
            },
            {
                "id": "prob-003",
                "title": "AI Explainability",
                "description_en": "Models lack explainability",
                "embedding_raw": "[" + ",".join(["0.1"] * 1536) + "]",
            },
        ]
    )
    return repo


@pytest.fixture
def problem_repo_empty() -> AsyncMock:
    repo = AsyncMock()
    repo.get_approved_with_embeddings = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def clustering_service(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo):
    return ClusteringService(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_clustering_skipped_with_fewer_than_3_problems(
    mock_llm_provider, problem_repo_empty, cluster_repo, tag_repo
) -> None:
    """Clustering is skipped and returns zero clusters when < 3 problems exist."""
    service = ClusteringService(mock_llm_provider, problem_repo_empty, cluster_repo, tag_repo)
    result = await service.run_clustering()

    assert result.clusters_updated == 0
    assert result.problems_processed == 0
    cluster_repo.upsert_cluster.assert_not_awaited()


async def test_hdbscan_is_called_with_embeddings(
    mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo
) -> None:
    """HDBSCAN receives a numpy array built from problem embeddings."""
    service = ClusteringService(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo)

    captured_arrays: list[np.ndarray] = []

    class MockHDBSCAN:
        def __init__(self, **kwargs):
            self.probabilities_ = np.array([1.0, 1.0, 1.0])

        def fit_predict(self, X: np.ndarray) -> np.ndarray:
            captured_arrays.append(X)
            # All in one cluster
            return np.array([0, 0, 0])

    with patch("app.services.clustering_service.hdbscan") as mock_hdbscan_module:
        mock_hdbscan_module.HDBSCAN = MockHDBSCAN
        await service.run_clustering()

    assert len(captured_arrays) == 1
    assert captured_arrays[0].shape == (3, 1536)


async def test_cluster_is_upserted_in_db(
    mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo
) -> None:
    """Discovered clusters are upserted in the cluster repository."""
    service = ClusteringService(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo)

    class MockHDBSCAN:
        def __init__(self, **kwargs):
            self.probabilities_ = np.array([1.0, 1.0, 1.0])

        def fit_predict(self, X: np.ndarray) -> np.ndarray:
            return np.array([0, 0, 0])

    with patch("app.services.clustering_service.hdbscan") as mock_hdbscan_module:
        mock_hdbscan_module.HDBSCAN = MockHDBSCAN
        await service.run_clustering()

    cluster_repo.upsert_cluster.assert_awaited_once()
    call_kwargs = cluster_repo.upsert_cluster.call_args
    assert call_kwargs.kwargs["label"] == "AI Governance"  # from mock_llm_provider


async def test_websocket_event_is_broadcast(
    mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo
) -> None:
    """A cluster.updated WebSocket event is broadcast for each cluster."""
    service = ClusteringService(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo)

    class MockHDBSCAN:
        def __init__(self, **kwargs):
            self.probabilities_ = np.array([1.0, 1.0, 1.0])

        def fit_predict(self, X: np.ndarray) -> np.ndarray:
            return np.array([0, 0, 0])

    broadcast_calls: list = []

    async def mock_broadcast(event):
        broadcast_calls.append(event)

    with patch("app.services.clustering_service.hdbscan") as mock_hdbscan_module:
        with patch(
            "app.services.clustering_service.websocket_service.broadcast",
            side_effect=mock_broadcast,
        ):
            mock_hdbscan_module.HDBSCAN = MockHDBSCAN
            await service.run_clustering()

    assert len(broadcast_calls) == 1
    assert broadcast_calls[0].type == "cluster.updated"


async def test_noise_points_excluded_from_clusters(
    mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo
) -> None:
    """Problems labeled -1 (noise) by HDBSCAN are not assigned to any cluster."""
    service = ClusteringService(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo)

    class MockHDBSCAN:
        def __init__(self, **kwargs):
            self.probabilities_ = np.array([1.0, 0.0, 1.0])

        def fit_predict(self, X: np.ndarray) -> np.ndarray:
            # prob-002 is noise
            return np.array([0, -1, 0])

    with patch("app.services.clustering_service.hdbscan") as mock_hdbscan_module:
        mock_hdbscan_module.HDBSCAN = MockHDBSCAN
        result = await service.run_clustering()

    assert result.clusters_updated == 1
    # Only 2 problems in the cluster (noise excluded)
    assign_calls = cluster_repo.assign_problem_to_cluster.call_args_list
    assigned_ids = [call.kwargs["problem_id"] for call in assign_calls]
    assert "prob-002" not in assigned_ids


async def test_clustering_result_contains_duration(
    mock_llm_provider, problem_repo_empty, cluster_repo, tag_repo
) -> None:
    """ClusteringResult always contains a non-negative duration_ms."""
    service = ClusteringService(mock_llm_provider, problem_repo_empty, cluster_repo, tag_repo)
    result = await service.run_clustering()

    assert isinstance(result.duration_ms, int)
    assert result.duration_ms >= 0


async def test_tags_are_persisted_and_linked_to_cluster(
    mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo
) -> None:
    """Tags returned by LLM are upserted and linked to the cluster via cluster_tag."""
    service = ClusteringService(mock_llm_provider, problem_repo_with_problems, cluster_repo, tag_repo)

    class MockHDBSCAN:
        def __init__(self, **kwargs):
            self.probabilities_ = np.array([1.0, 1.0, 1.0])

        def fit_predict(self, X: np.ndarray) -> np.ndarray:
            return np.array([0, 0, 0])

    with patch("app.services.clustering_service.hdbscan") as mock_hdbscan_module:
        mock_hdbscan_module.HDBSCAN = MockHDBSCAN
        await service.run_clustering()

    # mock_llm_provider.generate_tags returns [{"label": "AI Governance", "level": 1}]
    tag_repo.upsert_tag.assert_awaited_once_with(label="AI Governance", level=1)
    tag_repo.assign_tag_to_cluster.assert_awaited_once_with(
        cluster_id="cluster-uuid-001",
        tag_id="tag-uuid-001",
    )
