"""Module 8 — Error Handling.

Classifies API + tool errors, applies exponential backoff via tenacity, and
exposes a `self_correct` helper for feeding error context back to the model.
"""

from harness.errors.handlers import (
    HarnessError,
    ToolError,
    classify_anthropic_error,
    is_retryable,
    retry_anthropic,
    self_correct_prompt,
)

__all__ = [
    "HarnessError",
    "ToolError",
    "classify_anthropic_error",
    "is_retryable",
    "retry_anthropic",
    "self_correct_prompt",
]
