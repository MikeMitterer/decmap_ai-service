"""Contract tests for EmbeddingProvider implementations.

These tests verify that all providers satisfy the EmbeddingProvider contract.
They require real API keys and make actual network calls.

Run with: pytest tests/contract/ -v
Skipped automatically when API keys are not configured.
"""

import pytest

from app.config import settings
from app.providers.embedding.openai_provider import OpenAIEmbeddingProvider


def get_providers():
    """Collect all configured embedding providers for parametrized tests."""
    providers = []
    if settings.openai_api_key:
        providers.append(
            pytest.param(OpenAIEmbeddingProvider(settings), id="openai")
        )
    return providers


# ---------------------------------------------------------------------------
# Contract tests (require live API)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@pytest.mark.skipif(not settings.openai_api_key, reason="OPENAI_API_KEY not configured")
async def test_embed_returns_correct_dimensions(provider) -> None:
    """Provider returns 1536-dimensional vectors for a single text."""
    result = await provider.embed(["test text about AI governance"])

    assert len(result) == 1
    assert len(result[0]) == 1536


@pytest.mark.parametrize("provider", get_providers())
@pytest.mark.skipif(not settings.openai_api_key, reason="OPENAI_API_KEY not configured")
async def test_embed_multiple_texts(provider) -> None:
    """Provider returns one vector per input text."""
    texts = ["AI governance", "data quality problems", "model explainability"]
    result = await provider.embed(texts)

    assert len(result) == len(texts)
    for vector in result:
        assert len(vector) == 1536


@pytest.mark.parametrize("provider", get_providers())
@pytest.mark.skipif(not settings.openai_api_key, reason="OPENAI_API_KEY not configured")
async def test_embed_returns_floats(provider) -> None:
    """All values in the embedding vector are floats."""
    result = await provider.embed(["test"])

    assert all(isinstance(v, float) for v in result[0])


@pytest.mark.parametrize("provider", get_providers())
@pytest.mark.skipif(not settings.openai_api_key, reason="OPENAI_API_KEY not configured")
async def test_embed_similar_texts_have_high_cosine_similarity(provider) -> None:
    """Semantically similar texts produce similar embeddings."""
    import numpy as np

    texts = [
        "AI governance framework for companies",
        "Corporate AI governance and policies",
    ]
    result = await provider.embed(texts)

    vec1 = np.array(result[0])
    vec2 = np.array(result[1])
    cosine_sim = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    # Similar texts should have cosine similarity > 0.8
    assert cosine_sim > 0.8


# ---------------------------------------------------------------------------
# Contract tests (do NOT require live API — testing interface compliance)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@pytest.mark.skipif(not settings.openai_api_key, reason="OPENAI_API_KEY not configured")
async def test_embed_empty_list(provider) -> None:
    """Empty input list returns empty list without error."""
    result = await provider.embed([])

    assert result == []
