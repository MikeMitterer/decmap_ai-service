import json

import structlog
from anthropic import AsyncAnthropic

from app.config import Settings
from app.providers.llm.base import LLMProvider

logger = structlog.get_logger()

_SPAM_SYSTEM = (
    "You are a spam/bot detection system for a B2B AI problem-mapping platform. "
    "Users submit AI-related problems they face in their companies. "
    "Evaluate whether the given text is spam, bot-generated, or irrelevant. "
    "Respond with JSON: {\"is_spam\": bool, \"reason\": string}. "
    "reason is empty string when is_spam is false."
)

_TRANSLATE_SYSTEM = (
    "You are a professional translator. Translate the given JSON object "
    "from the specified source language into English. "
    "Preserve technical terminology. "
    "Return JSON with keys 'title_en' and 'description_en' only. No extra keys."
)

_SOLUTION_SYSTEM = (
    "You are an expert AI consultant helping SMEs solve AI adoption challenges. "
    "Write a concrete, actionable solution approach in Markdown format. "
    "Use headings, bullet points, and practical steps. "
    "Be concise (200-400 words). Focus on pragmatic implementation."
)

_TAGS_SYSTEM = (
    "You are a taxonomy expert for AI problem classification. "
    "Given a cluster of related AI problems from SMEs, generate 1-3 descriptive tags. "
    "Tags should be domain-level categories (e.g. 'AI Governance', 'Data Quality', "
    "'Change Management', 'Model Reliability'). "
    "Return JSON array: [{\"label\": string, \"level\": 1}]"
)


class AnthropicLLMProvider(LLMProvider):
    """LLM provider backed by Anthropic Claude Haiku."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.anthropic_model

    async def complete(self, prompt: str, system: str | None = None) -> str:
        kwargs: dict = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system

        response = await self._client.messages.create(**kwargs)
        content = response.content[0]
        if hasattr(content, "text"):
            return content.text
        return ""

    async def is_spam(self, text: str, signals: list[str]) -> tuple[bool, str]:
        log = logger.bind(provider="anthropic", operation="is_spam")
        prompt = (
            f"Behavioral signals detected: {signals}\n\n"
            f"Text to evaluate:\n{text}"
        )
        raw = await self.complete(prompt, system=_SPAM_SYSTEM)
        log.debug("spam_check_response", raw=raw)

        try:
            data = json.loads(raw)
            return bool(data.get("is_spam", False)), str(data.get("reason", ""))
        except (json.JSONDecodeError, KeyError):
            log.warning("spam_check_parse_error", raw=raw)
            return False, ""

    async def translate(
        self, title: str, description: str, source_lang: str
    ) -> tuple[str, str]:
        log = logger.bind(provider="anthropic", operation="translate", source_lang=source_lang)
        prompt = (
            f"Source language: {source_lang}\n\n"
            f"{json.dumps({'title': title, 'description': description}, ensure_ascii=False)}"
        )
        raw = await self.complete(prompt, system=_TRANSLATE_SYSTEM)
        log.debug("translation_response", raw=raw)

        try:
            data = json.loads(raw)
            return str(data["title_en"]), str(data["description_en"])
        except (json.JSONDecodeError, KeyError):
            log.warning("translation_parse_error", raw=raw)
            return title, description

    async def generate_solution(
        self, problem_title: str, problem_description: str
    ) -> str:
        log = logger.bind(provider="anthropic", operation="generate_solution")
        prompt = f"Problem: {problem_title}\n\nDescription:\n{problem_description}"
        solution = await self.complete(prompt, system=_SOLUTION_SYSTEM)
        log.debug("solution_generated", length=len(solution))
        return solution

    async def generate_tags(self, problems: list[dict]) -> list[dict]:
        log = logger.bind(provider="anthropic", operation="generate_tags", count=len(problems))
        summaries = [
            f"- {p.get('title', '')}: {p.get('description_en', '')[:200]}"
            for p in problems
        ]
        prompt = "Problems in this cluster:\n" + "\n".join(summaries)
        raw = await self.complete(prompt, system=_TAGS_SYSTEM)
        log.debug("tags_response", raw=raw)

        try:
            tags = json.loads(raw)
            if isinstance(tags, list):
                return tags
        except json.JSONDecodeError:
            log.warning("tags_parse_error", raw=raw)

        return [{"label": "Uncategorized", "level": 1}]
