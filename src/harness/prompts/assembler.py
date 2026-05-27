"""Prompt assembler.

Renders Jinja2 templates from ``src/harness/prompts/templates/`` into the system
prompt and any auxiliary context blocks. Templates have access to:

- ``persona`` — short string describing the agent
- ``tools`` — list of tool names available this run
- ``few_shots`` — list of {input, output} demonstrations
- ``extra`` — arbitrary dict passed by the caller

The default ``system.j2`` template is intentionally generic; specialize it for
your domain.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATE_DIR = Path(__file__).parent / "templates"


class PromptAssembler:
    def __init__(self, template_dir: Path | None = None) -> None:
        self._env = Environment(
            loader=FileSystemLoader(template_dir or TEMPLATE_DIR),
            autoescape=select_autoescape(),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def system_prompt(
        self,
        *,
        persona: str,
        tool_names: Iterable[str],
        few_shots: list[dict[str, str]] | None = None,
        extra: dict[str, Any] | None = None,
        template: str = "system.j2",
    ) -> str:
        tpl = self._env.get_template(template)
        return tpl.render(
            persona=persona,
            tools=list(tool_names),
            few_shots=few_shots or [],
            extra=extra or {},
        )
