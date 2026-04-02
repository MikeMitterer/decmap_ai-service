import structlog

from app.config import settings
from app.models.responses import SimilarityResult
from app.providers.embedding.base import EmbeddingProvider
from app.repositories.problem_repository import ProblemRepository

logger = structlog.get_logger()


class SimilarityService:
    """Finds problems similar to a given text using pgvector cosine similarity."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        problem_repo: ProblemRepository,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._problem_repo = problem_repo
        self._threshold = settings.similarity_threshold
        self._duplicate_threshold = settings.duplicate_threshold

    async def find_similar(self, text: str) -> SimilarityResult:
        """Find problems similar to the given text.

        1. Generate an embedding for the input text.
        2. Query pgvector for cosine-similar approved problems above threshold.
        3. Flag result as having duplicates if any score exceeds duplicate_threshold.

        Args:
            text: Short text to compare (problem title or submission).

        Returns:
            SimilarityResult with matched problems and duplicate flag.
        """
        log = logger.bind(
            threshold=self._threshold,
            duplicate_threshold=self._duplicate_threshold,
        )
        log.debug("similarity_check_started", text_length=len(text))

        embeddings = await self._embedding_provider.embed([text])
        embedding = embeddings[0]

        similar = await self._problem_repo.find_similar(embedding, self._threshold)

        has_duplicates = any(p.score > self._duplicate_threshold for p in similar)

        log.info(
            "similarity_check_complete",
            matches=len(similar),
            has_duplicates=has_duplicates,
        )
        return SimilarityResult(similar_problems=similar, has_duplicates=has_duplicates)
