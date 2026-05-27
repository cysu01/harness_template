"""Module 7 — State & Checkpoints.

SQLite-backed checkpoint store. Each checkpoint captures the agent's full
message history at a step boundary so a crashed run can resume — or so you can
inspect / replay (time-travel debugging).
"""

from harness.state.checkpoint import Checkpoint, CheckpointStore

__all__ = ["Checkpoint", "CheckpointStore"]
