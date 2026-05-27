"""Composable guardrails for input + output filtering and tool gating.

Each guardrail returns a :class:`GuardrailResult` indicating whether the content
passes, was modified, or must be blocked. A :class:`GuardrailPipeline` runs a
sequence of them and short-circuits on the first block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class GuardrailResult:
    allowed: bool
    content: str
    reason: str | None = None


class Guardrail(Protocol):
    def check(self, content: str) -> GuardrailResult: ...


class PIIScrubber:
    """Replace common PII patterns with placeholders. Heuristic — not GDPR-grade."""

    EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
    SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    CC = re.compile(r"\b(?:\d[ -]*?){13,16}\b")

    def check(self, content: str) -> GuardrailResult:
        cleaned = self.CC.sub("[REDACTED_CC]", content)
        cleaned = self.SSN.sub("[REDACTED_SSN]", cleaned)
        cleaned = self.EMAIL.sub("[REDACTED_EMAIL]", cleaned)
        cleaned = self.PHONE.sub("[REDACTED_PHONE]", cleaned)
        return GuardrailResult(
            allowed=True,
            content=cleaned,
            reason="PII scrubbed" if cleaned != content else None,
        )


class PromptInjectionFilter:
    """Trivial heuristic injection detector. Replace with a model-based scanner
    (LlamaGuard, Guardrails AI, etc.) for production use."""

    SUSPICIOUS = (
        "ignore previous instructions",
        "disregard the above",
        "you are now a different",
        "system prompt:",
        "<|im_start|>",
    )

    def check(self, content: str) -> GuardrailResult:
        lower = content.lower()
        for marker in self.SUSPICIOUS:
            if marker in lower:
                return GuardrailResult(
                    allowed=False,
                    content=content,
                    reason=f"possible prompt injection: {marker!r}",
                )
        return GuardrailResult(allowed=True, content=content)


class ToolAllowlist:
    """Filter tool invocations against a permitted set. Operates on tool names,
    not free text — instantiate per agent role (RBAC).
    """

    def __init__(self, allowed: set[str] | None) -> None:
        self.allowed = allowed  # None = wildcard

    def allows(self, tool_name: str) -> bool:
        return self.allowed is None or tool_name in self.allowed


class GuardrailPipeline:
    def __init__(self, guards: list[Guardrail]) -> None:
        self.guards = guards

    def check(self, content: str) -> GuardrailResult:
        current = content
        for guard in self.guards:
            result = guard.check(current)
            if not result.allowed:
                return result
            current = result.content
        return GuardrailResult(allowed=True, content=current)
