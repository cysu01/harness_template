"""Shared fixtures. Sets a dummy API key so config validation passes in CI."""

from __future__ import annotations

import os

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")
