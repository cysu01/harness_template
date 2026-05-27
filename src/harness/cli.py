"""Command-line entrypoint: `python -m harness.cli "your task"`."""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console

from harness.agent import Agent
from harness.tools.builtin import default_registry  # noqa: F401 — registers tools


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("task", nargs="?", help="The task to run")
    parser.add_argument("--session-id", help="Resume a previous session by id")
    parser.add_argument("--persona", default="You are a helpful, careful, autonomous agent.")
    args = parser.parse_args(argv)

    console = Console()
    if not args.task:
        console.print("[red]error:[/red] no task provided")
        parser.print_usage()
        return 2

    agent = Agent(persona=args.persona, session_id=args.session_id)
    result = asyncio.run(agent.run(args.task))

    console.rule(f"[bold]Session {result.session_id}[/bold]")
    console.print(result.final_text)
    console.rule("[dim]Usage[/dim]")
    console.print(
        f"iterations={result.iterations}  "
        f"input_tokens={result.usage.get('input_tokens', 0)}  "
        f"output_tokens={result.usage.get('output_tokens', 0)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
