import pytest

from app.models.responses import TranslationResult
from app.services.translation_service import TranslationService


@pytest.fixture
def service(mock_llm_provider) -> TranslationService:
    return TranslationService(mock_llm_provider)


async def test_translate_calls_llm_with_correct_args(service, mock_llm_provider) -> None:
    """translate() passes title, description and source_lang to the LLM provider."""
    await service.translate(
        title="KI-Governance fehlt",
        description="Keine Richtlinien für KI-Nutzung",
        source_lang="de",
    )

    mock_llm_provider.translate.assert_awaited_once_with(
        "KI-Governance fehlt",
        "Keine Richtlinien für KI-Nutzung",
        "de",
    )


async def test_translate_returns_translation_result(service, mock_llm_provider) -> None:
    """translate() wraps the LLM output in a TranslationResult."""
    mock_llm_provider.translate.return_value = (
        "AI Governance missing",
        "No policies for AI usage",
    )

    result = await service.translate(
        title="KI-Governance fehlt",
        description="Keine Richtlinien für KI-Nutzung",
        source_lang="de",
    )

    assert isinstance(result, TranslationResult)
    assert result.title_en == "AI Governance missing"
    assert result.description_en == "No policies for AI usage"


async def test_translate_skips_llm_for_english(service, mock_llm_provider) -> None:
    """English text is returned unchanged without calling the LLM."""
    result = await service.translate(
        title="AI Governance missing",
        description="No policies for AI usage",
        source_lang="en",
    )

    mock_llm_provider.translate.assert_not_awaited()
    assert result.title_en == "AI Governance missing"
    assert result.description_en == "No policies for AI usage"


async def test_translate_skips_llm_for_english_uppercase(service, mock_llm_provider) -> None:
    """'EN' (uppercase) is also treated as English."""
    await service.translate("Title", "Desc", source_lang="EN")
    mock_llm_provider.translate.assert_not_awaited()


async def test_translate_propagates_llm_values(service, mock_llm_provider) -> None:
    """TranslationResult fields are exactly what the LLM returns."""
    mock_llm_provider.translate.return_value = ("Translated Title", "Translated Desc")

    result = await service.translate("Titre", "Description", source_lang="fr")

    assert result.title_en == "Translated Title"
    assert result.description_en == "Translated Desc"
