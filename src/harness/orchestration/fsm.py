"""Finite state machine for deterministic workflows.

When the task can be expressed as fixed steps (e.g., classify → extract →
validate → format), an FSM is more predictable than a ReAct loop. Each state
runs a callable; the callable returns the next state name (or ``None`` to halt).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

StateHandler = Callable[[dict[str, Any]], Awaitable[str | None]]


@dataclass(slots=True)
class Transition:
    from_state: str
    to_state: str
    reason: str


class StateMachine:
    def __init__(self, *, initial: str) -> None:
        self.initial = initial
        self._states: dict[str, StateHandler] = {}
        self.transitions: list[Transition] = []

    def state(self, name: str):
        def decorator(handler: StateHandler) -> StateHandler:
            self._states[name] = handler
            return handler

        return decorator

    async def run(self, context: dict[str, Any]) -> dict[str, Any]:
        current = self.initial
        while current is not None:
            handler = self._states.get(current)
            if handler is None:
                raise ValueError(f"no handler registered for state {current!r}")
            next_state = await handler(context)
            self.transitions.append(
                Transition(
                    from_state=current,
                    to_state=next_state or "<halt>",
                    reason="ok",
                )
            )
            if next_state is None:
                break
            current = next_state
        return context
