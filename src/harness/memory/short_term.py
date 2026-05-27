"""Short-term memory — the conversation buffer for the current session.

Default is in-process. If `REDIS_URL` is set in config, swaps to Redis so the
buffer survives process restarts and can be shared across workers.
"""

from __future__ import annotations

import json
from typing import Any

from harness.config import settings


class ShortTermMemory:
    """Append-only message buffer keyed by session id."""

    def __init__(self, session_id: str, *, max_messages: int | None = None) -> None:
        self.session_id = session_id
        self.max_messages = max_messages
        self._backend: _Backend
        if settings.redis_url:
            self._backend = _RedisBackend(settings.redis_url, session_id)
        else:
            self._backend = _InMemoryBackend()

    def append(self, message: dict[str, Any]) -> None:
        self._backend.append(message)
        if self.max_messages is not None:
            self._backend.trim(self.max_messages)

    def extend(self, messages: list[dict[str, Any]]) -> None:
        for m in messages:
            self.append(m)

    def history(self) -> list[dict[str, Any]]:
        return self._backend.history()

    def clear(self) -> None:
        self._backend.clear()

    def __len__(self) -> int:
        return len(self.history())


class _Backend:
    def append(self, message: dict[str, Any]) -> None: ...
    def history(self) -> list[dict[str, Any]]: ...
    def trim(self, max_messages: int) -> None: ...
    def clear(self) -> None: ...


class _InMemoryBackend(_Backend):
    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []

    def append(self, message: dict[str, Any]) -> None:
        self._messages.append(message)

    def history(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def trim(self, max_messages: int) -> None:
        if len(self._messages) > max_messages:
            self._messages = self._messages[-max_messages:]

    def clear(self) -> None:
        self._messages.clear()


class _RedisBackend(_Backend):
    def __init__(self, url: str, session_id: str) -> None:
        try:
            import redis  # type: ignore[import-not-found]
        except ImportError as e:
            raise ImportError(
                "redis backend requested but `redis` is not installed; "
                "install with `pip install harness[redis]`"
            ) from e
        self._r = redis.Redis.from_url(url, decode_responses=True)
        self._key = f"harness:session:{session_id}:messages"

    def append(self, message: dict[str, Any]) -> None:
        self._r.rpush(self._key, json.dumps(message))

    def history(self) -> list[dict[str, Any]]:
        return [json.loads(m) for m in self._r.lrange(self._key, 0, -1)]

    def trim(self, max_messages: int) -> None:
        self._r.ltrim(self._key, -max_messages, -1)

    def clear(self) -> None:
        self._r.delete(self._key)
