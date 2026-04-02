from unittest.mock import MagicMock

import pytest

from app.providers.embedding.factory import create_embedding_provider
from app.providers.embedding.openai_provider import OpenAIEmbeddingProvider


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock()
    settings.openai_api_key = "sk-test-key"
    settings.openai_embedding_model = "text-embedding-3-small"
    return settings


def test_factory_returns_openai_provider_by_default(mock_settings) -> None:
    """Factory returns OpenAIEmbeddingProvider when embedding_provider='openai'."""
    mock_settings.embedding_provider = "openai"
    provider = create_embedding_provider(mock_settings)
    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_factory_returns_openai_provider_case_insensitive(mock_settings) -> None:
    """Provider name matching is case-insensitive."""
    mock_settings.embedding_provider = "OpenAI"
    provider = create_embedding_provider(mock_settings)
    assert isinstance(provider, OpenAIEmbeddingProvider)


def test_factory_raises_for_ollama(mock_settings) -> None:
    """Factory raises NotImplementedError for Ollama with a helpful message."""
    mock_settings.embedding_provider = "ollama"
    with pytest.raises(NotImplementedError) as exc_info:
        create_embedding_provider(mock_settings)

    assert "ollama" in str(exc_info.value).lower()
    assert "not yet implemented" in str(exc_info.value).lower()


def test_factory_raises_for_unknown_provider(mock_settings) -> None:
    """Factory raises NotImplementedError for any unknown provider name."""
    mock_settings.embedding_provider = "cohere"
    with pytest.raises(NotImplementedError) as exc_info:
        create_embedding_provider(mock_settings)

    assert "cohere" in str(exc_info.value)
    assert "openai" in str(exc_info.value).lower()
