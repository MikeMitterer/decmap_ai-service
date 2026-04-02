import pytest

from app.services.spam_filter_service import SpamFilterService


@pytest.fixture
def service(mock_llm_provider) -> SpamFilterService:
    return SpamFilterService(mock_llm_provider)


async def test_honeypot_filled_rejects_without_llm(service, mock_llm_provider) -> None:
    """Honeypot field being filled results in immediate rejection, no LLM call."""
    result = await service.evaluate(
        text="Some text",
        signals=[],
        honeypot="I am a bot",
    )

    assert result.status == "rejected"
    assert result.reason == "honeypot"
    mock_llm_provider.is_spam.assert_not_awaited()


async def test_two_signals_rejects_without_llm(service, mock_llm_provider) -> None:
    """Two or more behavioral signals result in rejection without LLM call."""
    result = await service.evaluate(
        text="Some text",
        signals=["fast_submit", "repeated_ip"],
        honeypot=None,
    )

    assert result.status == "rejected"
    assert result.reason == "multiple_signals"
    mock_llm_provider.is_spam.assert_not_awaited()


async def test_three_signals_rejects_without_llm(service, mock_llm_provider) -> None:
    """Three signals also trigger rejection without LLM."""
    result = await service.evaluate(
        text="Some text",
        signals=["fast_submit", "repeated_ip", "known_bad_agent"],
        honeypot=None,
    )

    assert result.status == "rejected"
    mock_llm_provider.is_spam.assert_not_awaited()


async def test_one_signal_needs_review_without_llm(service, mock_llm_provider) -> None:
    """One behavioral signal triggers needs_review state without LLM call."""
    result = await service.evaluate(
        text="Some text",
        signals=["fast_submit"],
        honeypot=None,
    )

    assert result.status == "needs_review"
    assert result.reason == "suspicious_signal"
    mock_llm_provider.is_spam.assert_not_awaited()


async def test_zero_signals_llm_says_spam_rejects(service, mock_llm_provider) -> None:
    """Zero signals + LLM returns spam=True → rejected."""
    mock_llm_provider.is_spam.return_value = (True, "promotional_content")

    result = await service.evaluate(
        text="Buy cheap SEO services! Click here!",
        signals=[],
        honeypot=None,
    )

    assert result.status == "rejected"
    assert result.reason == "promotional_content"
    mock_llm_provider.is_spam.assert_awaited_once()


async def test_zero_signals_llm_says_ok_pending(service, mock_llm_provider) -> None:
    """Zero signals + LLM returns spam=False → pending (approved for moderation)."""
    mock_llm_provider.is_spam.return_value = (False, "")

    result = await service.evaluate(
        text="We have trouble implementing AI governance in our SME.",
        signals=[],
        honeypot=None,
    )

    assert result.status == "pending"
    assert result.reason is None
    mock_llm_provider.is_spam.assert_awaited_once()


async def test_signals_are_propagated_in_result(service, mock_llm_provider) -> None:
    """The signals list is always returned in the FilterResult."""
    signals = ["fast_submit"]
    result = await service.evaluate(text="text", signals=signals, honeypot=None)

    assert result.signals == signals


async def test_empty_honeypot_string_is_treated_as_no_honeypot(
    service, mock_llm_provider
) -> None:
    """An empty string honeypot value should not trigger rejection."""
    mock_llm_provider.is_spam.return_value = (False, "")

    result = await service.evaluate(
        text="Legitimate problem text",
        signals=[],
        honeypot="",
    )

    # Empty string is falsy in Python — should not reject
    assert result.status == "pending"
