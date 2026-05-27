"""Long-term memory — pluggable vector store interface.

Default implementation is an in-process cosine-similarity store using whatever
embedding function the caller supplies. Swap in Pinecone / Weaviate / Chroma by
implementing `LongTermMemory`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

EmbedFn = Callable[[str], list[float]]


@dataclass(slots=True)
class MemoryRecord:
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class LongTermMemory(Protocol):
    """Interface every long-term backend must implement."""

    def add(self, text: str, *, metadata: dict[str, Any] | None = None) -> str: ...
    def search(self, query: str, *, k: int = 5) -> list[MemoryRecord]: ...
    def delete(self, record_id: str) -> None: ...


class InMemoryVectorMemory:
    """Reference implementation. Not for production-scale recall."""

    def __init__(self, embed_fn: EmbedFn) -> None:
        self._embed = embed_fn
        self._store: dict[str, MemoryRecord] = {}
        self._counter = 0

    def add(self, text: str, *, metadata: dict[str, Any] | None = None) -> str:
        self._counter += 1
        record_id = f"mem_{self._counter}"
        self._store[record_id] = MemoryRecord(
            text=text,
            embedding=self._embed(text),
            metadata=metadata or {},
        )
        return record_id

    def search(self, query: str, *, k: int = 5) -> list[MemoryRecord]:
        if not self._store:
            return []
        q = self._embed(query)
        scored = [(_cosine(q, r.embedding), r) for r in self._store.values()]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:k]]

    def delete(self, record_id: str) -> None:
        self._store.pop(record_id, None)


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
