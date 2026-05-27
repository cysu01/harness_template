"""Checkpoint store backed by SQLite.

A checkpoint is a (session_id, step) tuple that holds the message history and
arbitrary metadata. Storage is JSON-on-disk; SQLite gives us atomic writes and
indexed lookup for cheap.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness.config import settings


@dataclass(slots=True)
class Checkpoint:
    session_id: str
    step: int
    messages: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class CheckpointStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.checkpoint_db
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoints (
                session_id TEXT NOT NULL,
                step       INTEGER NOT NULL,
                messages   TEXT NOT NULL,
                metadata   TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (session_id, step)
            )
            """
        )

    def save(self, checkpoint: Checkpoint) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?, ?, ?)",
            (
                checkpoint.session_id,
                checkpoint.step,
                json.dumps(checkpoint.messages),
                json.dumps(checkpoint.metadata),
                checkpoint.created_at,
            ),
        )

    def latest(self, session_id: str) -> Checkpoint | None:
        row = self._conn.execute(
            "SELECT session_id, step, messages, metadata, created_at "
            "FROM checkpoints WHERE session_id = ? ORDER BY step DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        return _row_to_checkpoint(row) if row else None

    def at_step(self, session_id: str, step: int) -> Checkpoint | None:
        row = self._conn.execute(
            "SELECT session_id, step, messages, metadata, created_at "
            "FROM checkpoints WHERE session_id = ? AND step = ?",
            (session_id, step),
        ).fetchone()
        return _row_to_checkpoint(row) if row else None

    def list_sessions(self) -> list[str]:
        return [
            row[0]
            for row in self._conn.execute(
                "SELECT DISTINCT session_id FROM checkpoints ORDER BY session_id"
            )
        ]

    def steps(self, session_id: str) -> list[int]:
        return [
            row[0]
            for row in self._conn.execute(
                "SELECT step FROM checkpoints WHERE session_id = ? ORDER BY step",
                (session_id,),
            )
        ]


def _row_to_checkpoint(row: tuple[Any, ...]) -> Checkpoint:
    session_id, step, messages, metadata, created_at = row
    return Checkpoint(
        session_id=session_id,
        step=step,
        messages=json.loads(messages),
        metadata=json.loads(metadata),
        created_at=created_at,
    )
