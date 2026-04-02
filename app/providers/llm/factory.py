import structlog

from app.config import Settings
from app.providers.llm.anthropic_provider import AnthropicLLMProvider
from app.providers.llm.base import LLMProvider
from app.providers.llm.openai_provider import OpenAILLMProvider

logger = structlog.get_logger()


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Instantiate the configured LLM provider.

    Reads `settings.llm_provider` to select the backend.
    Supported values:
        - "openai" (default): OpenAI GPT-4o-mini
        - "anthropic": Anthropic Claude Haiku

    Args:
        settings: Application settings instance.

    Returns:
        An LLMProvider ready for use.

    Raises:
        NotImplementedError: If `llm_provider` is an unknown value.
    """
    provider_name = settings.llm_provider.lower()
    log = logger.bind(llm_provider=provider_name)

    if provider_name == "openai":
        log.info("llm_provider_selected", provider="openai")
        return OpenAILLMProvider(settings)

    if provider_name == "anthropic":
        log.info("llm_provider_selected", provider="anthropic")
        return AnthropicLLMProvider(settings)

    raise NotImplementedError(
        f"Unknown LLM provider: '{provider_name}'. "
        f"Supported values: 'openai', 'anthropic'. Set LLM_PROVIDER in your .env file."
    )
