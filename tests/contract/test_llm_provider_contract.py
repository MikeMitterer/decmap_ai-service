"""Contract tests for LLMProvider implementations.

These tests verify that all providers satisfy the LLMProvider contract.
They require real API keys and make actual network calls.

Run with: pytest tests/contract/ -v
Skipped automatically when API keys are not configured.
"""

import pytest

from app.config import settings
from app.providers.llm.anthropic_provider import AnthropicLLMProvider
from app.providers.llm.openai_provider import OpenAILLMProvider


def get_providers():
    """Collect all configured LLM providers for parametrized tests."""
    providers = []
    if settings.openai_api_key:
        providers.append(pytest.param(OpenAILLMProvider(settings), id="openai"))
    if settings.anthropic_api_key:
        providers.append(pytest.param(AnthropicLLMProvider(settings), id="anthropic"))
    return providers


skip_if_no_keys = pytest.mark.skipif(
    not (settings.openai_api_key or settings.anthropic_api_key),
    reason="No LLM API keys configured",
)


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_complete_returns_string(provider) -> None:
    """complete() returns a non-empty string."""
    result = await provider.complete("Say 'ok' and nothing else.")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_complete_with_system_prompt(provider) -> None:
    """complete() accepts and uses a system prompt."""
    result = await provider.complete(
        prompt="What are you?",
        system="You are a helpful AI assistant. Keep responses to one sentence.",
    )
    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# is_spam()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_is_spam_returns_tuple(provider) -> None:
    """is_spam() returns (bool, str) tuple."""
    is_spam, reason = await provider.is_spam(
        text="We have no AI governance in our SME",
        signals=[],
    )
    assert isinstance(is_spam, bool)
    assert isinstance(reason, str)


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_is_spam_rejects_obvious_spam(provider) -> None:
    """is_spam() correctly identifies obvious spam content."""
    is_spam, reason = await provider.is_spam(
        text="Buy cheap Rolex watches! Click here for 90% off! Limited time offer!",
        signals=[],
    )
    assert is_spam is True


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_is_spam_approves_legitimate_content(provider) -> None:
    """is_spam() does not flag legitimate business AI problems."""
    is_spam, _ = await provider.is_spam(
        text="Our company lacks a clear AI governance framework. "
             "Departments are adopting AI tools without oversight.",
        signals=[],
    )
    assert is_spam is False


# ---------------------------------------------------------------------------
# translate()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_translate_returns_tuple_of_strings(provider) -> None:
    """translate() returns (str, str) with non-empty values."""
    title_en, desc_en = await provider.translate(
        title="KI-Governance fehlt",
        description="Keine klaren Richtlinien für KI-Einsatz im Unternehmen.",
        source_lang="de",
    )
    assert isinstance(title_en, str)
    assert isinstance(desc_en, str)
    assert len(title_en) > 0
    assert len(desc_en) > 0


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_translate_german_to_english(provider) -> None:
    """German text is translated to English."""
    title_en, desc_en = await provider.translate(
        title="Datenschutz bei KI",
        description="Wir verarbeiten personenbezogene Daten ohne DSGVO-Konformität.",
        source_lang="de",
    )
    # Basic sanity: response should not be in German
    assert "Datenschutz" not in title_en
    assert len(title_en) > 3


# ---------------------------------------------------------------------------
# generate_solution()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_generate_solution_returns_markdown(provider) -> None:
    """generate_solution() returns a non-trivial Markdown string."""
    result = await provider.generate_solution(
        problem_title="Lack of AI governance framework",
        problem_description=(
            "Our company has no clear policies for AI usage, "
            "leading to shadow AI adoption by individual departments."
        ),
    )
    assert isinstance(result, str)
    assert len(result) > 100  # Should be a substantive response


# ---------------------------------------------------------------------------
# generate_tags()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_generate_tags_returns_list(provider) -> None:
    """generate_tags() returns a list of tag dicts."""
    problems = [
        {
            "title": "Lack of AI governance",
            "description_en": "No policies for AI usage",
        }
    ]
    result = await provider.generate_tags(problems)

    assert isinstance(result, list)
    assert len(result) >= 1


@pytest.mark.parametrize("provider", get_providers())
@skip_if_no_keys
async def test_generate_tags_have_required_fields(provider) -> None:
    """Each tag dict has 'label' (str) and 'level' (int) fields."""
    problems = [
        {"title": "Data quality issues", "description_en": "Inconsistent training data"}
    ]
    tags = await provider.generate_tags(problems)

    for tag in tags:
        assert "label" in tag
        assert "level" in tag
        assert isinstance(tag["label"], str)
        assert isinstance(tag["level"], int)
