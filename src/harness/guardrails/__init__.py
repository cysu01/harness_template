"""Module 9 — Guardrails.

Two-sided filtering:
- **Input** — PII scrubbing, prompt-injection heuristic detection.
- **Output** — content checks, tool-call gating via an allowlist (RBAC).

Designed to compose: stack multiple ``Guardrail`` instances and the pipeline
short-circuits on the first block.
"""

from harness.guardrails.filters import (
    Guardrail,
    GuardrailPipeline,
    GuardrailResult,
    PIIScrubber,
    PromptInjectionFilter,
    ToolAllowlist,
)

__all__ = [
    "Guardrail",
    "GuardrailPipeline",
    "GuardrailResult",
    "PIIScrubber",
    "PromptInjectionFilter",
    "ToolAllowlist",
]
