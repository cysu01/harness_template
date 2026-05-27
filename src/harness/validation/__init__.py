"""Module 10 — Validation & Feedback.

Verifies the agent's output. Three built-in validators:
- ``CommandValidator`` — runs a shell command (pytest, ruff, mypy, etc.).
- ``JudgeLLM`` — uses a separate Claude model as grader.
- ``CompositeValidator`` — chains multiple validators with AND/OR logic.
"""

from harness.validation.judge import (
    CommandValidator,
    CompositeValidator,
    JudgeLLM,
    Validator,
    ValidatorResult,
)

__all__ = [
    "CommandValidator",
    "CompositeValidator",
    "JudgeLLM",
    "Validator",
    "ValidatorResult",
]
