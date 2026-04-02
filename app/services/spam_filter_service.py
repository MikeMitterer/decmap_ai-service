import structlog

from app.models.responses import FilterResult
from app.providers.llm.base import LLMProvider

logger = structlog.get_logger()


class SpamFilterService:
    """Multi-layer spam and bot detection.

    Evaluation order:
    1. Honeypot field filled → immediate reject (no LLM call)
    2. Two or more behavioral signals → reject (no LLM call)
    3. One behavioral signal → needs_review (no LLM call)
    4. Zero signals → LLM evaluation
    """

    def __init__(self, llm_provider: LLMProvider) -> None:
        self._llm_provider = llm_provider

    async def evaluate(
        self, text: str, signals: list[str], honeypot: str | None
    ) -> FilterResult:
        """Evaluate a submission for spam/bot indicators.

        Args:
            text: Combined title + description of the submitted problem.
            signals: List of detected behavioral signals
                     (e.g. ["fast_submit", "repeated_ip"]).
            honeypot: Content of the honeypot field (None or empty = clean).

        Returns:
            FilterResult with status one of: "pending", "needs_review", "rejected".
        """
        log = logger.bind(signal_count=len(signals), has_honeypot=bool(honeypot))

        if honeypot:
            log.info("spam_rejected", reason="honeypot")
            return FilterResult(status="rejected", reason="honeypot", signals=signals)

        if len(signals) >= 2:
            log.info("spam_rejected", reason="multiple_signals", signals=signals)
            return FilterResult(
                status="rejected", reason="multiple_signals", signals=signals
            )

        if len(signals) == 1:
            log.info("spam_needs_review", reason="suspicious_signal", signals=signals)
            return FilterResult(
                status="needs_review", reason="suspicious_signal", signals=signals
            )

        # Zero signals — delegate to LLM for final judgement
        is_spam, reason = await self._llm_provider.is_spam(text, signals)

        if is_spam:
            log.info("spam_rejected_by_llm", reason=reason)
            return FilterResult(status="rejected", reason=reason, signals=signals)

        log.debug("spam_check_passed")
        return FilterResult(status="pending", reason=None, signals=signals)
