"""Error classification + retry primitives.

We classify errors in three buckets:

- **Retryable** — rate limit, overloaded, transient network. tenacity backs off.
- **Auth / config** — bad API key, missing model. Fail fast; no retry.
- **Logic** — tool returned an error, schema mismatch. Surface via
  ``self_correct_prompt`` so the model can fix its own mistake.
"""

from __future__ import annotations

import logging
from typing import Any

import anthropic
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


class HarnessError(Exception):
    """Base class for harness-level errors that escape the loop."""


class ToolError(HarnessError):
    """A tool execution failed in a way the agent could not recover from."""


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, anthropic.RateLimitError | anthropic.APIConnectionError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code >= 500
    return False


def classify_anthropic_error(exc: BaseException) -> str:
    if isinstance(exc, anthropic.AuthenticationError):
        return "authentication"
    if isinstance(exc, anthropic.PermissionDeniedError):
        return "permission"
    if isinstance(exc, anthropic.NotFoundError):
        return "not_found"
    if isinstance(exc, anthropic.BadRequestError):
        return "bad_request"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limit"
    if isinstance(exc, anthropic.APIConnectionError):
        return "connection"
    if isinstance(exc, anthropic.APIStatusError):
        return "server" if exc.status_code >= 500 else "client"
    return "unknown"


def _log_retry(retry_state: RetryCallState) -> None:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc:
        logger.warning(
            "retry %d/%d after %s: %s",
            retry_state.attempt_number,
            retry_state.retry_object.stop.max_attempt_number,  # type: ignore[union-attr]
            type(exc).__name__,
            exc,
        )


def retry_anthropic(*, max_attempts: int = 5, min_wait: float = 1.0, max_wait: float = 30.0):
    """Decorator: retry Anthropic API calls with exponential backoff.

    Usage::

        @retry_anthropic()
        def call():
            return client.messages.create(...)
    """
    return retry(
        retry=retry_if_exception(is_retryable),
        wait=wait_exponential(multiplier=min_wait, max=max_wait),
        stop=stop_after_attempt(max_attempts),
        reraise=True,
        before_sleep=_log_retry,
    )


def self_correct_prompt(error_summary: str, *, attempt: int) -> dict[str, Any]:
    """Build a user-turn message instructing the model to fix its prior output."""
    return {
        "role": "user",
        "content": (
            f"Your previous attempt failed (attempt {attempt}):\n\n"
            f"```\n{error_summary}\n```\n\n"
            "Analyze the cause and try again. Do not repeat the exact same approach."
        ),
    }
