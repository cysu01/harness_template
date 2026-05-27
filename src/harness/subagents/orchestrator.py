"""Sub-agent patterns.

``SubAgent`` is a lightweight wrapper around a single ``messages.create`` call
with its own system prompt, tool registry, and model. The :class:`Coordinator`
fans tasks out to multiple sub-agents and aggregates their text responses.
"""

from __future__ import annotations

import asyncio
import copy
from dataclasses import dataclass
from typing import Any

from anthropic import Anthropic

from harness.config import settings
from harness.errors import retry_anthropic
from harness.tools import ToolRegistry


@dataclass(slots=True)
class SubAgentResult:
    name: str
    output: str
    usage: dict[str, int]


class SubAgent:
    """A single-turn worker. Specialize via ``system`` and ``tools``."""

    def __init__(
        self,
        name: str,
        client: Anthropic,
        *,
        system: str,
        model: str | None = None,
        tools: ToolRegistry | None = None,
        max_tokens: int = 4000,
    ) -> None:
        self.name = name
        self.client = client
        self.system = system
        self.model = model or settings.subagent_model
        self.tools = tools
        self.max_tokens = max_tokens

    async def run(self, task: str) -> SubAgentResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.system,
            "messages": [{"role": "user", "content": task}],
        }
        if self.tools is not None:
            kwargs["tools"] = self.tools.schemas()

        response = await asyncio.to_thread(self._call, kwargs)
        text = next(
            (b.text for b in response.content if getattr(b, "type", None) == "text"),
            "",
        )
        return SubAgentResult(
            name=self.name,
            output=text,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )

    @retry_anthropic()
    def _call(self, kwargs: dict[str, Any]):
        return self.client.messages.create(**kwargs)


class Coordinator:
    """Run multiple sub-agents on the same or different tasks in parallel."""

    def __init__(self, sub_agents: list[SubAgent]) -> None:
        self.sub_agents = sub_agents

    async def fan_out(self, task: str) -> list[SubAgentResult]:
        return await asyncio.gather(*(sa.run(task) for sa in self.sub_agents))

    async def assign(self, assignments: dict[str, str]) -> list[SubAgentResult]:
        by_name = {sa.name: sa for sa in self.sub_agents}
        tasks = [by_name[name].run(task) for name, task in assignments.items() if name in by_name]
        return await asyncio.gather(*tasks)


def fork(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return an independent deep copy of a message history for parallel exploration."""
    return copy.deepcopy(messages)


def handoff(
    *,
    from_messages: list[dict[str, Any]],
    target_persona: str,
    handoff_note: str,
) -> tuple[str, list[dict[str, Any]]]:
    """Prepare a handoff to a specialist agent.

    Returns ``(new_system_prompt, new_messages)``: the conversation is rendered
    into a context block prepended to a fresh user message describing the
    handoff. The receiving agent starts with no prior assistant turns.
    """
    rendered = _render_handoff_context(from_messages)
    new_messages = [
        {
            "role": "user",
            "content": (
                f"<handoff_context>\n{rendered}\n</handoff_context>\n\n"
                f"<handoff_note>\n{handoff_note}\n</handoff_note>"
            ),
        }
    ]
    return target_persona, new_messages


def _render_handoff_context(messages: list[dict[str, Any]]) -> str:
    out: list[str] = []
    for m in messages:
        role = m.get("role", "?")
        content = m.get("content", "")
        if isinstance(content, str):
            out.append(f"[{role}] {content}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    out.append(f"[{role}] {block.get('text', '')}")
    return "\n".join(out)
