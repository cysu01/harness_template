"""Module 6 — Structured Output.

Forces Claude to emit JSON conforming to a Pydantic model. Provides
``parse_response`` for the common case and ``extract_json`` as a regex fallback
when working with non-JSON-mode models.
"""

from harness.output.structured import StructuredCaller, extract_json

__all__ = ["StructuredCaller", "extract_json"]
