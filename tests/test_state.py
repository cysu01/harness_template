"""Tests for Module 7 — State & Checkpoints."""

from __future__ import annotations

from harness.state import Checkpoint, CheckpointStore


def test_save_and_latest(tmp_path):
    store = CheckpointStore(path=tmp_path / "ckpt.db")
    store.save(Checkpoint(session_id="s1", step=1, messages=[{"role": "user", "content": "hi"}]))
    store.save(Checkpoint(session_id="s1", step=2, messages=[{"role": "assistant", "content": "ok"}]))

    latest = store.latest("s1")
    assert latest is not None
    assert latest.step == 2
    assert latest.messages[0]["content"] == "ok"


def test_time_travel_at_specific_step(tmp_path):
    store = CheckpointStore(path=tmp_path / "ckpt.db")
    for i in range(1, 6):
        store.save(Checkpoint(session_id="s", step=i, messages=[{"step": i}]))

    snapshot = store.at_step("s", 3)
    assert snapshot is not None
    assert snapshot.messages == [{"step": 3}]


def test_list_sessions(tmp_path):
    store = CheckpointStore(path=tmp_path / "ckpt.db")
    store.save(Checkpoint(session_id="a", step=1, messages=[]))
    store.save(Checkpoint(session_id="b", step=1, messages=[]))
    sessions = store.list_sessions()
    assert sessions == ["a", "b"]
