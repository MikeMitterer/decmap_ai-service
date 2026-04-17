"""Unit tests for webhook auth and rate-limit config."""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.dependencies import verify_webhook_secret


# ---------------------------------------------------------------------------
# verify_webhook_secret
# ---------------------------------------------------------------------------


def test_verify_webhook_secret_passes_when_no_secret_configured() -> None:
    """Dev mode: no secret configured → any request passes."""
    with patch("app.dependencies.settings") as mock_settings:
        mock_settings.webhook_secret = ""
        # Should not raise
        verify_webhook_secret(x_webhook_secret=None)
        verify_webhook_secret(x_webhook_secret="anything")


def test_verify_webhook_secret_raises_401_when_header_missing() -> None:
    """Production mode: missing header → 401."""
    with patch("app.dependencies.settings") as mock_settings:
        mock_settings.webhook_secret = "supersecret"
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_secret(x_webhook_secret=None)
    assert exc_info.value.status_code == 401


def test_verify_webhook_secret_raises_401_when_header_wrong() -> None:
    """Production mode: wrong secret → 401."""
    with patch("app.dependencies.settings") as mock_settings:
        mock_settings.webhook_secret = "supersecret"
        with pytest.raises(HTTPException) as exc_info:
            verify_webhook_secret(x_webhook_secret="wrong")
    assert exc_info.value.status_code == 401


def test_verify_webhook_secret_passes_with_correct_secret() -> None:
    """Production mode: correct secret → no exception."""
    with patch("app.dependencies.settings") as mock_settings:
        mock_settings.webhook_secret = "supersecret"
        # Should not raise
        verify_webhook_secret(x_webhook_secret="supersecret")


# ---------------------------------------------------------------------------
# Rate limit config
# ---------------------------------------------------------------------------


def test_similarity_rate_limit_has_default_value() -> None:
    """similarity_rate_limit is set to a non-empty default."""
    from app.config import settings

    assert settings.similarity_rate_limit
    assert "/" in settings.similarity_rate_limit  # format: "<n>/<period>"
