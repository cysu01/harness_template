"""Multi-agent research example using the Coordinator pattern.

A `manager` agent breaks a research question into sub-questions and delegates
each to a `worker` sub-agent. Worker outputs are collated and returned.

Run:
    python examples/research_agent.py "Compare LangChain and LlamaIndex on tool use."
"""

from __future__ import annotations

import asyncio
import sys

from anthropic import Anthropic

from harness.config import settings
from harness.subagents import Coordinator, SubAgent


async def research(question: str) -> str:
    client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    # Three specialists with different angles.
    workers = [
        SubAgent(
            name="historian",
            client=client,
            system="You analyze the history and evolution of a topic. Be concise.",
        ),
        SubAgent(
            name="critic",
            client=client,
            system="You play devil's advocate. Find the weaknesses and risks. Be concise.",
        ),
        SubAgent(
            name="synthesizer",
            client=client,
            system="You write tight executive summaries. 4-bullet max.",
        ),
    ]
    coordinator = Coordinator(workers)
    results = await coordinator.fan_out(question)

    return "\n\n".join(f"## {r.name}\n{r.output}" for r in results)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python examples/research_agent.py "<question>"', file=sys.stderr)
        sys.exit(1)
    print(asyncio.run(research(" ".join(sys.argv[1:]))))
