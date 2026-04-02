import structlog
from openai import AsyncOpenAI

from app.config import Settings
from app.providers.embedding.base import EmbeddingProvider

logger = structlog.get_logger()


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by OpenAI text-embedding-3-small (1536 dims)."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_embedding_model

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via OpenAI embeddings API.

        Args:
            texts: List of strings to embed. Empty list returns empty list immediately.

        Returns:
            List of 1536-dimensional embedding vectors.
        """
        if not texts:
            return []

        log = logger.bind(provider="openai", model=self._model, count=len(texts))
        log.debug("generating_embeddings")

        response = await self._client.embeddings.create(
            model=self._model,
            input=texts,
        )

        embeddings = [item.embedding for item in response.data]
        log.debug("embeddings_generated", count=len(embeddings))
        return embeddings
