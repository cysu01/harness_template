"""Structured output via Pydantic + ``messages.parse``.

For Claude models that support output_config.format (Opus 4.6+, Sonnet 4.6+,
Haiku 4.5), this is the most reliable way to get JSON back. We use the SDK's
``messages.parse()`` helper, which validates against the supplied Pydantic
model automatically.

For older models or unstructured responses, ``extract_json`` does a best-effort
extraction from a text blob.
"""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from anthropic import Anthropic
from pydantic import BaseModel

from harness.config import settings

T = TypeVar("T", bound=BaseModel)


class StructuredCaller:
    """Wraps ``client.messages.parse`` with sensible defaults."""

    def __init__(self, client: Anthropic) -> None:
        self.client = client

    def call(
        self,
        *,
        schema: type[T],
        messages: list[dict[str, Any]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> T:
        response = self.client.messages.parse(
            model=model or settings.model,
            max_tokens=max_tokens or settings.max_tokens,
            system=system,
            messages=messages,
            output_format=schema,
        )
        if response.parsed_output is None:
            raise ValueError(
                f"Model did not return parseable {schema.__name__}; "
                f"stop_reason={response.stop_reason}"
            )
        return response.parsed_output


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_RAW_JSON = re.compile(r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})", re.DOTALL)


def extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of a free-form text response.

    Tries fenced blocks first, then any balanced ``{...}``. Returns ``None`` if
    nothing parses cleanly.
    """
    for pattern in (_JSON_BLOCK, _RAW_JSON):
        for match in pattern.finditer(text):
            try:
                return json.loads(match.group(1))
            except (json.JSONDecodeError, IndexError):
                continue
    return None
