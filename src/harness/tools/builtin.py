"""A handful of safe, generic built-in tools. Specialize for your domain."""

from __future__ import annotations

from pathlib import Path

from harness.tools.registry import default_registry, tool


@tool(parallel_safe=True)
def read_file(path: str) -> str:
    """Read a UTF-8 text file from the working directory and return its contents."""
    p = Path(path).resolve()
    if not _is_within_cwd(p):
        return f"PERMISSION_DENIED: {path} is outside the working directory"
    if not p.exists():
        return f"FILE_NOT_FOUND: {path}"
    return p.read_text(encoding="utf-8", errors="replace")


@tool(parallel_safe=True)
def list_directory(path: str = ".") -> list[str]:
    """List entries in a directory (non-recursive)."""
    p = Path(path).resolve()
    if not _is_within_cwd(p):
        return [f"PERMISSION_DENIED: {path}"]
    if not p.is_dir():
        return [f"NOT_A_DIRECTORY: {path}"]
    return sorted(entry.name for entry in p.iterdir())


@tool()
def write_file(path: str, content: str) -> str:
    """Write a UTF-8 text file. Overwrites existing files. Creates parent directories."""
    p = Path(path).resolve()
    if not _is_within_cwd(p):
        return f"PERMISSION_DENIED: {path}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"WROTE: {path} ({len(content)} bytes)"


def _is_within_cwd(p: Path) -> bool:
    try:
        p.relative_to(Path.cwd().resolve())
        return True
    except ValueError:
        return False


__all__ = ["default_registry", "list_directory", "read_file", "write_file"]
