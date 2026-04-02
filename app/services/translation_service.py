import structlog

from app.models.responses import TranslationResult
from app.providers.llm.base import LLMProvider

logger = structlog.get_logger()


class TranslationService:
    """Translates problem titles and descriptions into English via LLM."""

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def translate(
        self, title: str, description: str, source_lang: str
    ) -> TranslationResult:
        """Translate a problem title and description into English.

        Skips the LLM call if source_lang is already 'en'.

        Args:
            title: Original problem title.
            description: Original problem description.
            source_lang: ISO 639-1 language code (e.g. "de", "fr").

        Returns:
            TranslationResult with title_en and description_en.
        """
        log = logger.bind(source_lang=source_lang)

        if source_lang.lower() == "en":
            log.debug("translation_skipped_already_english")
            return TranslationResult(title_en=title, description_en=description)

        log.debug("translation_started")
        title_en, description_en = await self._llm_provider.translate(
            title, description, source_lang
        )

        log.info("translation_complete", source_lang=source_lang)
        return TranslationResult(title_en=title_en, description_en=description_en)
