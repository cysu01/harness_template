"""Module 11 — Sub-Agent Orchestration.

Three patterns:
- **Fork** — duplicate the parent's context for a parallel exploration.
- **Handoff** — transfer the task token to a specialist; the original agent
  steps out.
- **Teammate (coordinator)** — a manager agent fans tasks out to workers and
  collates the results.
"""

from harness.subagents.orchestrator import Coordinator, SubAgent, fork, handoff

__all__ = ["Coordinator", "SubAgent", "fork", "handoff"]
