"""Minimal usage example.

Run:
    python examples/basic_agent.py "List the files in src/harness and summarize what each module does."
"""

from __future__ import annotations

import asyncio
import sys

from harness import Agent

# Importing builtin tools registers them on the default registry.
from harness.tools import builtin  # noqa: F401


async def main(task: str) -> None:
    agent = Agent(
        persona=(
            "You are a careful code-reading assistant. When asked about a "
            "codebase, use the file-system tools to ground your answers in real "
            "content rather than guessing."
        ),
    )
    result = await agent.run(task)
    print("\n=== RESULT ===\n")
    print(result.final_text)
    print(f"\n(iterations={result.iterations}, tokens={result.usage})")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python examples/basic_agent.py "<task>"', file=sys.stderr)
        sys.exit(1)
    asyncio.run(main(" ".join(sys.argv[1:])))
