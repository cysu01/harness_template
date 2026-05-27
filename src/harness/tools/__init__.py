"""Module 2 — Tooling Layer.

Pydantic-validated tool registry. Tools are plain Python functions decorated
with `@tool`; the registry derives their JSON schema, dispatches calls, and
returns results in the shape Claude expects.
"""

from harness.tools.registry import Tool, ToolRegistry, default_registry, tool

__all__ = ["Tool", "ToolRegistry", "default_registry", "tool"]
