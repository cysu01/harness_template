"""Tests for Module 2 — Tooling Layer."""

from __future__ import annotations

import asyncio
import time

import pytest

from harness.tools import Tool, ToolRegistry


def test_register_and_dispatch_sync():
    registry = ToolRegistry()

    def add(a: int, b: int) -> int:
        """Add two integers."""
        return a + b

    registry.register(add)
    assert "add" in registry.names()


@pytest.mark.asyncio
async def test_dispatch_runs_function():
    registry = ToolRegistry()

    def echo(text: str) -> str:
        """Echo the input."""
        return text.upper()

    registry.register(echo)
    result = await registry.dispatch("echo", {"text": "hi"})
    assert result == "HI"


@pytest.mark.asyncio
async def test_validation_error_is_returned_not_raised():
    registry = ToolRegistry()

    def needs_int(n: int) -> int:
        """Need integer."""
        return n * 2

    registry.register(needs_int)
    result = await registry.dispatch("needs_int", {"n": "not-an-int"})
    assert result.startswith("INPUT_VALIDATION_ERROR")


@pytest.mark.asyncio
async def test_parallel_dispatch_runs_concurrently():
    registry = ToolRegistry()

    async def slow(x: int) -> int:
        """Slow doubler."""

        await asyncio.sleep(0.05)
        return x * 2

    registry.register(slow, parallel_safe=True)

    start = time.perf_counter()
    results = await registry.dispatch_parallel(
        [("slow", {"x": 1}), ("slow", {"x": 2}), ("slow", {"x": 3})]
    )
    elapsed = time.perf_counter() - start
    assert results == ["2", "4", "6"]
    # If serial, would be ~0.15s; parallel should be ~0.05s.
    assert elapsed < 0.12


def test_unknown_tool_returns_error():
    registry = ToolRegistry()
    result = asyncio.run(registry.dispatch("nope", {}))
    assert result.startswith("TOOL_NOT_FOUND")


def test_tool_schema_shape():
    registry = ToolRegistry()

    def t(name: str, count: int = 1) -> str:
        """A test tool."""
        return f"{name}*{count}"

    tool: Tool = registry.register(t)
    schema = tool.schema()
    assert schema["name"] == "t"
    assert schema["description"] == "A test tool."
    assert "input_schema" in schema
    assert "name" in schema["input_schema"]["properties"]
