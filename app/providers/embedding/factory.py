import structlog

from app.config import Settings
from app.providers.embedding.base import EmbeddingProvider
from app.providers.embedding.openai_provider import OpenAIEmbeddingProvider

logger = structlog.get_logger()


def create_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Instantiate the configured embedding provider.

    Reads `settings.embedding_provider` to select the backend.
    Supported values:
        - "openai" (default): OpenAI text-embedding-3-small
        - "ollama": Not yet implemented — raises NotImplementedError

    Args:
        settings: Application settings instance.

    Returns:
        An EmbeddingProvider ready for use.

    Raises:
        NotImplementedError: If `embedding_provider` is "ollama" or unknown.
    """
    provider_name = settings.embedding_provider.lower()
    log = logger.bind(embedding_provider=provider_name)

    if provider_name == "openai":
        log.info("embedding_provider_selected", provider="openai")
        return OpenAIEmbeddingProvider(settings)

    if provider_name == "ollama":
        raise NotImplementedError(
            "Ollama embedding provider is not yet implemented. "
            "To add support, create app/providers/embedding/ollama_provider.py "
            "implementing the EmbeddingProvider ABC and register it here."
        )

    raise NotImplementedError(
        f"Unknown embedding provider: '{provider_name}'. "
        f"Supported values: 'openai'. Set EMBEDDING_PROVIDER in your .env file."
    )
