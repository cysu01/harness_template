"""ReAct loop — the agent's main control flow.

Each iteration:
1. Call ``messages.create`` with the full conversation, tools, and system prompt.
2. If ``stop_reason == "end_turn"``: we're done.
3. If ``stop_reason == "tool_use"``: dispatch the tool calls (in parallel when
   all are parallel-safe) and append the results as a user turn.
4. Otherwise raise — unhandled stop reason.

The loop hands off to other modules at well-defined points:
- :mod:`harness.errors` wraps the API call in tenacity retry.
- :mod:`harness.context` rebalances the message history when it grows large.
- :mod:`harness.state` saves a checkpoint per iteration.
- :mod:`harness.guardrails` filters tool dispatch.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from anthropic import Anthropic

from harness.config import settings
from harness.context import ContextManager
from harness.errors import HarnessError, retry_anthropic
from harness.guardrails import ToolAllowlist
from harness.state import Checkpoint, CheckpointStore
from harness.tools import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoopResult:
    session_id: str
    final_text: str
    messages: list[dict[str, Any]]
    iterations: int
    stop_reason: str
    usage: dict[str, int] = field(default_factory=dict)


class ReActLoop:
    def __init__(
        self,
        client: Anthropic,
        *,
        tools: ToolRegistry,
        system: str,
        context_manager: ContextManager | None = None,
        checkpoint_store: CheckpointStore | None = None,
        tool_allowlist: ToolAllowlist | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        max_iterations: int | None = None,
        session_id: str | None = None,
    ) -> None:
        self.client = client
        self.tools = tools
        self.system = system
        self.context = context_manager or ContextManager(client)
        self.checkpoints = checkpoint_store
        self.tool_allowlist = tool_allowlist or ToolAllowlist(settings.allowed_tool_set())
        self.model = model or settings.model
        self.max_tokens = max_tokens or settings.max_tokens
        self.max_iterations = max_iterations or settings.max_iterations
        self.session_id = session_id or uuid.uuid4().hex

    async def run(self, user_input: str) -> LoopResult:
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_input}]
        usage_total = {"input_tokens": 0, "output_tokens": 0}

        for step in range(1, self.max_iterations + 1):
            messages = self.context.maybe_compact(messages, system=self.system)
            response = self._call_api(messages)

            usage_total["input_tokens"] += response.usage.input_tokens
            usage_total["output_tokens"] += response.usage.output_tokens

            messages.append({"role": "assistant", "content": response.content})
            self._checkpoint(step, messages)

            stop_reason = response.stop_reason
            logger.debug("step=%d stop_reason=%s", step, stop_reason)

            if stop_reason == "end_turn":
                final_text = _extract_text(response.content)
                return LoopResult(
                    session_id=self.session_id,
                    final_text=final_text,
                    messages=messages,
                    iterations=step,
                    stop_reason=stop_reason,
                    usage=usage_total,
                )

            if stop_reason == "tool_use":
                tool_results = await self._handle_tool_calls(response.content)
                messages.append({"role": "user", "content": tool_results})
                continue

            if stop_reason == "pause_turn":
                # Server-side tool needs another round-trip; loop again as-is.
                continue

            if stop_reason == "max_tokens":
                raise HarnessError("hit max_tokens; increase HARNESS_MAX_TOKENS or stream")

            if stop_reason == "refusal":
                final_text = _extract_text(response.content)
                return LoopResult(
                    session_id=self.session_id,
                    final_text=final_text or "[refused]",
                    messages=messages,
                    iterations=step,
                    stop_reason=stop_reason,
                    usage=usage_total,
                )

            raise HarnessError(f"unhandled stop_reason: {stop_reason}")

        raise HarnessError(f"max iterations ({self.max_iterations}) exceeded")

    @retry_anthropic()
    def _call_api(self, messages: list[dict[str, Any]]):
        allowed = self.tool_allowlist.allowed
        tool_schemas = self.tools.schemas(allowed=allowed)
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system,
            "messages": messages,
        }
        if tool_schemas:
            kwargs["tools"] = tool_schemas
        if settings.thinking == "adaptive":
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": settings.effort}
        return self.client.messages.create(**kwargs)

    async def _handle_tool_calls(self, content: list[Any]) -> list[dict[str, Any]]:
        calls: list[tuple[str, dict[str, Any], str]] = []
        for block in content:
            if getattr(block, "type", None) != "tool_use":
                continue
            name = block.name
            if not self.tool_allowlist.allows(name):
                calls.append((name, block.input, block.id))
                continue
            calls.append((name, block.input, block.id))

        outputs = await self.tools.dispatch_parallel([(n, i) for n, i, _ in calls])

        results: list[dict[str, Any]] = []
        for (name, _input, tool_use_id), output in zip(calls, outputs, strict=True):
            allowed = self.tool_allowlist.allows(name)
            if not allowed:
                output = f"TOOL_BLOCKED_BY_ALLOWLIST: {name}"
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": output,
                    "is_error": (not allowed) or output.startswith(("INPUT_VALIDATION_ERROR", "TOOL_NOT_FOUND")),
                }
            )
        return results

    def _checkpoint(self, step: int, messages: list[dict[str, Any]]) -> None:
        if self.checkpoints is None:
            return
        # ContentBlock objects aren't JSON-serializable as-is; normalize.
        normalized = [_normalize_message(m) for m in messages]
        self.checkpoints.save(
            Checkpoint(session_id=self.session_id, step=step, messages=normalized)
        )


def _extract_text(content: list[Any]) -> str:
    return "\n".join(
        b.text for b in content if getattr(b, "type", None) == "text"
    ).strip()


def _normalize_message(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("content")
    if isinstance(content, str):
        return message
    if isinstance(content, list):
        new: list[Any] = []
        for block in content:
            if isinstance(block, dict):
                new.append(block)
            else:
                # Anthropic SDK content block — dump to dict
                if hasattr(block, "model_dump"):
                    new.append(block.model_dump())
                else:
                    new.append({"type": getattr(block, "type", "unknown"), "value": str(block)})
        return {**message, "content": new}
    return message
