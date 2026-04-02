from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: List of strings to embed. Empty list returns empty list.

        Returns:
            List of embedding vectors. Each vector has the same dimension
            as defined by the underlying model (e.g. 1536 for text-embedding-3-small).
        """
        ...
