"""The Agent facade composes the 12 modules into a single entrypoint.

Most callers should only need to instantiate :class:`Agent` and call
``run(user_input)``. To customize, pass in alternate instances of any module
through the constructor — every dependency is optional and has a sensible
default.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from anthropic import Anthropic

from harness.config import settings
from harness.context import ContextManager
from harness.env import configure_logging, ensure_sandbox
from harness.guardrails import (
    Guardrail,
    GuardrailPipeline,
    PIIScrubber,
    PromptInjectionFilter,
    ToolAllowlist,
)
from harness.memory import ShortTermMemory
from harness.orchestration import LoopResult, ReActLoop
from harness.prompts import PromptAssembler
from harness.state import CheckpointStore
from harness.tools import ToolRegistry, default_registry
from harness.validation import Validator

logger = logging.getLogger(__name__)


class Agent:
    """Top-level agent that composes all 12 modules."""

    def __init__(
        self,
        *,
        persona: str = "You are a helpful, careful, autonomous agent.",
        tools: ToolRegistry | None = None,
        client: Anthropic | None = None,
        session_id: str | None = None,
        input_guards: list[Guardrail] | None = None,
        output_guards: list[Guardrail] | None = None,
        validator: Validator | None = None,
        max_validation_attempts: int = 3,
        few_shots: list[dict[str, str]] | None = None,
        extra_system_context: dict[str, Any] | None = None,
        skip_env_check: bool = False,
    ) -> None:
        configure_logging()
        if not skip_env_check:
            ensure_sandbox(strict=False)

        self.persona = persona
        self.client = client or Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
        self.tools = tools or default_registry
        self.session_id = session_id or uuid.uuid4().hex

        self.assembler = PromptAssembler()
        self.system = self.assembler.system_prompt(
            persona=persona,
            tool_names=self.tools.names(),
            few_shots=few_shots,
            extra=extra_system_context,
        )

        # Module 9 — guardrails
        default_input_guards: list[Guardrail] = [PromptInjectionFilter()]
        if settings.pii_scrub:
            default_input_guards.append(PIIScrubber())
        self.input_guards = GuardrailPipeline(input_guards or default_input_guards)
        self.output_guards = GuardrailPipeline(output_guards or [])

        # Module 3 — memory
        self.memory = ShortTermMemory(self.session_id)

        # Module 7 — checkpoints
        self.checkpoints = CheckpointStore()

        # Module 10 — validator (optional)
        self.validator = validator
        self.max_validation_attempts = max_validation_attempts

        # Module 1 — the loop
        self.loop = ReActLoop(
            client=self.client,
            tools=self.tools,
            system=self.system,
            context_manager=ContextManager(self.client),
            checkpoint_store=self.checkpoints,
            tool_allowlist=ToolAllowlist(settings.allowed_tool_set()),
            session_id=self.session_id,
        )

    async def run(self, user_input: str) -> LoopResult:
        # Module 9 — input guardrails
        input_check = self.input_guards.check(user_input)
        if not input_check.allowed:
            raise ValueError(f"input blocked: {input_check.reason}")

        attempt = 0
        last_result: LoopResult | None = None
        feedback_prefix = ""

        while attempt < self.max_validation_attempts:
            attempt += 1
            prompt = f"{feedback_prefix}{input_check.content}" if feedback_prefix else input_check.content
            result = await self.loop.run(prompt)
            last_result = result

            # Module 9 — output guardrails
            output_check = self.output_guards.check(result.final_text)
            if not output_check.allowed:
                feedback_prefix = (
                    f"Your previous output was blocked by a guardrail "
                    f"({output_check.reason}). Try a different approach.\n\n"
                )
                continue

            result.final_text = output_check.content

            # Module 10 — validation
            if self.validator is None:
                return result
            verdict = self.validator.validate(task=user_input, output=result.final_text)
            if verdict.passed:
                return result
            logger.info("validator failed (attempt %d): %s", attempt, verdict.feedback)
            feedback_prefix = (
                f"Your previous attempt failed validation. Feedback:\n{verdict.feedback}\n\n"
                "Address the feedback and try again.\n\n"
            )

        assert last_result is not None
        return last_result

    @property
    def system_prompt(self) -> str:
        return self.system
