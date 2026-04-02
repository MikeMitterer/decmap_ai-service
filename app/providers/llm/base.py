from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract base class for all LLM providers."""

    @abstractmethod
    async def complete(self, prompt: str, system: str | None = None) -> str:
        """Send a completion request to the LLM.

        Args:
            prompt: The user message / prompt.
            system: Optional system prompt to set context/persona.

        Returns:
            The model's text response.
        """
        ...

    @abstractmethod
    async def is_spam(self, text: str, signals: list[str]) -> tuple[bool, str]:
        """Evaluate whether a text submission is spam or bot-generated.

        Args:
            text: The problem title + description to evaluate.
            signals: List of behavioral signals already detected (e.g. "fast_submit").

        Returns:
            Tuple of (is_spam: bool, reason: str).
            reason is empty string when is_spam is False.
        """
        ...

    @abstractmethod
    async def translate(
        self, title: str, description: str, source_lang: str
    ) -> tuple[str, str]:
        """Translate a problem title and description into English.

        Args:
            title: Original problem title.
            description: Original problem description.
            source_lang: ISO 639-1 language code of the source text (e.g. "de").

        Returns:
            Tuple of (title_en: str, description_en: str).
        """
        ...

    @abstractmethod
    async def generate_solution(
        self, problem_title: str, problem_description: str
    ) -> str:
        """Generate an AI solution approach for a given problem.

        Args:
            problem_title: Title of the problem.
            problem_description: Full description of the problem.

        Returns:
            Markdown-formatted solution approach text.
        """
        ...

    @abstractmethod
    async def generate_tags(self, problems: list[dict]) -> list[dict]:
        """Generate descriptive tags for a cluster of problems.

        Args:
            problems: List of problem dicts with at least 'title' and 'description_en' keys.

        Returns:
            List of tag dicts with 'label' (str) and 'level' (int) keys.
            Level 1 = top-level domain tag (AI Governance, Data Quality, etc.)
        """
        ...
