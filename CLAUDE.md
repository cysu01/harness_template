# Project Guidance for Claude Code

This repository is a **template** for building Claude-powered agents. The architecture is intentionally modular — every concern lives in its own subpackage under `src/harness/`.

## What this is

A scaffold, not a working product. The 12 modules expose small, opinionated interfaces; users specialize them for their domain. Treat them as the framework, not the application.

## Working in this codebase

- **Respect the module boundaries.** If you're tempted to import from a sibling module's private internals, add a method to the public interface instead.
- **Anthropic SDK is the only LLM dependency.** Don't add OpenAI, LangChain, or LlamaIndex. Wrapper layers exist for things we deliberately abstract (e.g., long-term memory backend), but Claude itself is called directly via the SDK.
- **Default model is `claude-opus-4-7`** with adaptive thinking. Don't downgrade for cost without explicit user direction.
- **Streaming is the default** for any request that may exceed ~16K output tokens.
- **All tools are validated through Pydantic.** Don't bypass `tool_registry.register()` and pass raw JSON Schemas.

## Files you'll touch most

- `src/harness/agent.py` — the orchestrator that composes every module
- `src/harness/orchestration/react_loop.py` — main ReAct loop
- `src/harness/tools/builtin.py` — where new tools go
- `src/harness/config.py` — adding settings

## Testing

```bash
pytest                    # full suite
pytest -k orchestration   # narrow
pytest --cov=harness      # coverage
```

The harness is designed so each module can be tested in isolation. Always add a unit test under `tests/test_<module>.py` when you change behavior.

## Anti-patterns to avoid

- Catching `Exception` instead of using `harness.errors` classification.
- Adding global mutable state — checkpoints exist for a reason.
- Hard-coding model strings outside `config.py`.
- Adding `time.sleep` to "wait for things" — use the tenacity retry helpers in `harness.errors`.
