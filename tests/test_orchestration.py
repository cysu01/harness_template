"""Tests for Module 1 — Orchestration Loop (focused on FSM since ReAct needs API)."""

from __future__ import annotations

import pytest

from harness.orchestration import StateMachine


@pytest.mark.asyncio
async def test_fsm_runs_to_completion():
    machine = StateMachine(initial="start")

    @machine.state("start")
    async def _start(ctx):
        ctx["visited"] = ["start"]
        return "middle"

    @machine.state("middle")
    async def _middle(ctx):
        ctx["visited"].append("middle")
        return "end"

    @machine.state("end")
    async def _end(ctx):
        ctx["visited"].append("end")
        return None

    result = await machine.run({})
    assert result["visited"] == ["start", "middle", "end"]
    assert len(machine.transitions) == 3


@pytest.mark.asyncio
async def test_fsm_raises_for_unknown_state():
    machine = StateMachine(initial="start")

    @machine.state("start")
    async def _start(ctx):
        return "nowhere"

    with pytest.raises(ValueError, match="no handler"):
        await machine.run({})
