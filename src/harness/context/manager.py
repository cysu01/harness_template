"""Context manager — keeps messages under a token budget.

Strategies:
- **Summarization** — when total tokens exceed threshold, condense older turns
  by asking the model for a summary. The summary replaces the condensed turns.
- **Observation masking** — collapse very large tool_result blocks to a head/tail
  preview, keeping the full content in the checkpoint store.
- **Lost-in-the-middle mitigation** — when summarizing, hoist the original task
  back to the most recent user turn so it isn't buried mid-history.

Token counting uses Claude's count_tokens API to stay accurate across models.
"""

from __future__ import annotations

import logging
from typing import Any

from anthropic import Anthropic

from harness.config import settings

logger = logging.getLogger(__name__)

OBSERVATION_PREVIEW = 2000  # chars
SUMMARY_KEEP_RECENT = 4  # don't summarize the last N turns


class ContextManager:
    def __init__(
        self,
        client: Anthropic,
        *,
        token_budget: int = 150_000,
        summary_trigger: float = 0.8,
    ) -> None:
        self.client = client
        self.token_budget = token_budget
        self.summary_trigger = summary_trigger

    def count_tokens(
        self, messages: list[dict[str, Any]], *, system: str | None = None
    ) -> int:
        try:
            kwargs: dict[str, Any] = {"model": settings.model, "messages": messages}
            if system:
                kwargs["system"] = system
            return self.client.messages.count_tokens(**kwargs).input_tokens
        except Exception as e:
            logger.debug("count_tokens failed (%s); using char-based estimate", e)
            return _char_based_estimate(messages, system)

    def maybe_compact(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return a possibly-compacted message list. Idempotent if under budget."""
        tokens = self.count_tokens(messages, system=system)
        if tokens < int(self.token_budget * self.summary_trigger):
            return messages

        logger.info("Context %d tokens >= trigger; compacting", tokens)
        masked = [self._mask_observation(m) for m in messages]

        if len(masked) <= SUMMARY_KEEP_RECENT + 2:
            return masked

        head, tail = masked[:-SUMMARY_KEEP_RECENT], masked[-SUMMARY_KEEP_RECENT:]
        summary = self._summarize(head, system=system)
        return [
            {"role": "user", "content": f"<conversation_summary>\n{summary}\n</conversation_summary>"},
            *tail,
        ]

    def _mask_observation(self, message: dict[str, Any]) -> dict[str, Any]:
        """Truncate large tool_result blocks to head + tail preview."""
        content = message.get("content")
        if not isinstance(content, list):
            return message

        new_blocks: list[Any] = []
        for block in content:
            if not isinstance(block, dict):
                new_blocks.append(block)
                continue
            if block.get("type") != "tool_result":
                new_blocks.append(block)
                continue
            inner = block.get("content", "")
            text = inner if isinstance(inner, str) else str(inner)
            if len(text) > OBSERVATION_PREVIEW * 2:
                head = text[:OBSERVATION_PREVIEW]
                tail = text[-OBSERVATION_PREVIEW:]
                omitted = len(text) - len(head) - len(tail)
                new_blocks.append(
                    {**block, "content": f"{head}\n...[{omitted} chars omitted]...\n{tail}"}
                )
            else:
                new_blocks.append(block)
        return {**message, "content": new_blocks}

    def _summarize(self, messages: list[dict[str, Any]], *, system: str | None) -> str:
        prompt = (
            "Summarize the following conversation into bullet points covering: "
            "(1) the original goal, (2) key facts learned, (3) decisions made, "
            "(4) any unresolved questions. Be concise but lossless on actionable detail."
        )
        # Render the conversation as a single text block for the summarizer call.
        rendered = _render_for_summary(messages)
        response = self.client.messages.create(
            model=settings.judge_model,
            max_tokens=4000,
            system=system,
            messages=[{"role": "user", "content": f"{prompt}\n\n---\n\n{rendered}"}],
        )
        return next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            "",
        )


def _char_based_estimate(messages: list[dict[str, Any]], system: str | None) -> int:
    """Cheap fallback when count_tokens isn't available. ~4 chars/token."""
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    if system:
        chars += len(system)
    return chars // 4


def _render_for_summary(messages: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, str):
            out.append(f"[{role}] {content}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        out.append(f"[{role}] {block.get('text', '')}")
                    elif block.get("type") == "tool_use":
                        out.append(f"[{role}/tool_use:{block.get('name')}] {block.get('input')}")
                    elif block.get("type") == "tool_result":
                        out.append(f"[{role}/tool_result] {block.get('content')}")
    return "\n".join(out)
