"""Module 12 (Init & Environment) — settings loaded from .env via pydantic-settings.

Single source of truth for runtime configuration. Every module reads from `settings`;
nothing else reaches into `os.environ` directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]
ThinkingMode = Literal["adaptive", "disabled"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_prefix="",
    )

    anthropic_api_key: SecretStr = Field(..., alias="ANTHROPIC_API_KEY")

    model: str = Field("claude-opus-4-7", alias="HARNESS_MODEL")
    judge_model: str = Field("claude-sonnet-4-6", alias="HARNESS_JUDGE_MODEL")
    subagent_model: str = Field("claude-haiku-4-5", alias="HARNESS_SUBAGENT_MODEL")

    max_tokens: int = Field(16000, alias="HARNESS_MAX_TOKENS")
    effort: Effort = Field("high", alias="HARNESS_EFFORT")
    thinking: ThinkingMode = Field("adaptive", alias="HARNESS_THINKING")

    max_iterations: int = Field(25, alias="HARNESS_MAX_ITERATIONS")
    parallel_tools: bool = Field(True, alias="HARNESS_PARALLEL_TOOLS")

    checkpoint_db: Path = Field(Path("./.harness/checkpoints.db"), alias="HARNESS_CHECKPOINT_DB")
    log_level: str = Field("INFO", alias="HARNESS_LOG_LEVEL")

    redis_url: str | None = Field(None, alias="REDIS_URL")
    vector_db_url: str | None = Field(None, alias="VECTOR_DB_URL")

    pii_scrub: bool = Field(True, alias="HARNESS_PII_SCRUB")
    allowed_tools: str = Field("*", alias="HARNESS_ALLOWED_TOOLS")

    def allowed_tool_set(self) -> set[str] | None:
        """Return None for wildcard, else the parsed allowlist."""
        if self.allowed_tools.strip() == "*":
            return None
        return {name.strip() for name in self.allowed_tools.split(",") if name.strip()}


settings = Settings()  # type: ignore[call-arg]
