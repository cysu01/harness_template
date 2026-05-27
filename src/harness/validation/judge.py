"""Validators that decide whether an agent's output is acceptable.

The :class:`Validator` protocol is intentionally small — anything that maps
``(task, output) → ValidatorResult`` qualifies. Use the result's ``passed`` flag
to decide whether to accept or to feed ``feedback`` back into the agent loop.
"""

from __future__ import annotations

import logging
import shlex
import subprocess
from dataclasses import dataclass
from typing import Protocol

from anthropic import Anthropic
from pydantic import BaseModel, Field

from harness.config import settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ValidatorResult:
    passed: bool
    feedback: str
    score: float | None = None


class Validator(Protocol):
    def validate(self, *, task: str, output: str) -> ValidatorResult: ...


class CommandValidator:
    """Runs a shell command and treats exit code 0 as pass.

    Stdout + stderr are captured and forwarded as feedback on failure so the
    agent has actionable error context (pytest output, lint complaints).
    """

    def __init__(self, command: str, *, cwd: str | None = None, timeout: float = 60.0) -> None:
        self.command = command
        self.cwd = cwd
        self.timeout = timeout

    def validate(self, *, task: str, output: str) -> ValidatorResult:
        del task, output  # unused; the command inspects the filesystem
        try:
            proc = subprocess.run(
                shlex.split(self.command),
                cwd=self.cwd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ValidatorResult(
                passed=False, feedback=f"command timed out: {self.command!r}"
            )
        if proc.returncode == 0:
            return ValidatorResult(passed=True, feedback="ok")
        return ValidatorResult(
            passed=False,
            feedback=f"exit={proc.returncode}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}",
        )


class _JudgeVerdict(BaseModel):
    passed: bool = Field(description="True if the output satisfies the task")
    score: float = Field(description="Quality score from 0.0 to 1.0")
    feedback: str = Field(description="Specific, actionable critique")


class JudgeLLM:
    """A separate Claude model grades the output. Cheaper than the primary model."""

    def __init__(self, client: Anthropic, *, model: str | None = None) -> None:
        self.client = client
        self.model = model or settings.judge_model

    def validate(self, *, task: str, output: str) -> ValidatorResult:
        prompt = (
            "Evaluate whether this output satisfies the task. Be strict but fair.\n\n"
            f"<task>\n{task}\n</task>\n\n"
            f"<output>\n{output}\n</output>"
        )
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            output_format=_JudgeVerdict,
        )
        verdict = response.parsed_output
        if verdict is None:
            return ValidatorResult(passed=False, feedback="judge model failed to parse")
        return ValidatorResult(
            passed=verdict.passed, feedback=verdict.feedback, score=verdict.score
        )


class CompositeValidator:
    """Combine multiple validators. ``mode='all'`` requires every check to pass;
    ``mode='any'`` accepts when at least one passes."""

    def __init__(self, validators: list[Validator], *, mode: str = "all") -> None:
        if mode not in {"all", "any"}:
            raise ValueError("mode must be 'all' or 'any'")
        self.validators = validators
        self.mode = mode

    def validate(self, *, task: str, output: str) -> ValidatorResult:
        results = [v.validate(task=task, output=output) for v in self.validators]
        passed_all = all(r.passed for r in results)
        passed_any = any(r.passed for r in results)
        ok = passed_all if self.mode == "all" else passed_any
        feedback = "\n---\n".join(f"[{i}] {r.feedback}" for i, r in enumerate(results))
        return ValidatorResult(passed=ok, feedback=feedback)
