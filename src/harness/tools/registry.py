"""Tool registry — declarative tool definitions backed by Pydantic.

Tools are registered via `@tool` (decorator) or `ToolRegistry.register(...)`.
The registry produces the JSON Schema sent to Claude and dispatches tool_use
blocks to the right Python callable.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError, create_model

ToolFn = Callable[..., Any] | Callable[..., Awaitable[Any]]


@dataclass(slots=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: ToolFn
    parallel_safe: bool = False

    def schema(self) -> dict[str, Any]:
        """Render as a Claude tool definition."""
        schema = self.input_model.model_json_schema()
        # Strip Pydantic-only fields Claude doesn't need.
        schema.pop("title", None)
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": schema,
        }

    async def call(self, raw_input: dict[str, Any]) -> str:
        """Validate input, dispatch, and serialize the result to a string."""
        try:
            validated = self.input_model.model_validate(raw_input)
        except ValidationError as e:
            return f"INPUT_VALIDATION_ERROR: {e.errors()}"

        kwargs = validated.model_dump()
        result = self.fn(**kwargs)
        if inspect.iscoroutine(result):
            result = await result

        if isinstance(result, str):
            return result
        try:
            return json.dumps(result, default=str)
        except (TypeError, ValueError):
            return str(result)


class ToolRegistry:
    """Holds all tools available to an agent. Tools are name-keyed."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        fn: ToolFn,
        *,
        name: str | None = None,
        description: str | None = None,
        parallel_safe: bool = False,
    ) -> Tool:
        tool_name = name or fn.__name__
        if tool_name in self._tools:
            raise ValueError(f"Tool {tool_name!r} already registered")

        input_model = _infer_input_model(fn, tool_name)
        doc = description or (fn.__doc__ or "").strip()
        if not doc:
            raise ValueError(f"Tool {tool_name!r} has no description (docstring or arg)")

        t = Tool(
            name=tool_name,
            description=doc,
            input_model=input_model,
            fn=fn,
            parallel_safe=parallel_safe,
        )
        self._tools[tool_name] = t
        return t

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def schemas(self, allowed: set[str] | None = None) -> list[dict[str, Any]]:
        """Return Claude-compatible tool schemas, optionally filtered by allowlist."""
        return [
            t.schema()
            for name, t in self._tools.items()
            if allowed is None or name in allowed
        ]

    def names(self) -> list[str]:
        return list(self._tools)

    async def dispatch(self, name: str, raw_input: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if tool is None:
            return f"TOOL_NOT_FOUND: {name}"
        return await tool.call(raw_input)

    async def dispatch_parallel(
        self, calls: list[tuple[str, dict[str, Any]]]
    ) -> list[str]:
        """Run multiple tool calls concurrently when all of them are parallel-safe."""
        all_safe = all(
            (t := self._tools.get(name)) is not None and t.parallel_safe
            for name, _ in calls
        )
        if all_safe and len(calls) > 1:
            return await asyncio.gather(*(self.dispatch(n, i) for n, i in calls))
        # Sequential fallback preserves ordering for non-parallel-safe tools.
        return [await self.dispatch(n, i) for n, i in calls]


def _infer_input_model(fn: ToolFn, name: str) -> type[BaseModel]:
    """Build a Pydantic model from the function signature."""
    sig = inspect.signature(fn)
    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else str
        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[param_name] = (annotation, default)
    return create_model(f"{name}_Input", **fields)


def tool(
    *,
    name: str | None = None,
    description: str | None = None,
    parallel_safe: bool = False,
    registry: ToolRegistry | None = None,
) -> Callable[[ToolFn], ToolFn]:
    """Decorator. Registers the function with the default or supplied registry.

    Usage::

        @tool(parallel_safe=True)
        def search(query: str) -> str:
            '''Search the web.'''
            ...
    """
    target = registry if registry is not None else default_registry

    def decorator(fn: ToolFn) -> ToolFn:
        target.register(fn, name=name, description=description, parallel_safe=parallel_safe)
        return fn

    return decorator


default_registry = ToolRegistry()
