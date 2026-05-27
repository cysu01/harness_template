"""Tests for Module 6 — Structured Output (regex fallback path)."""

from __future__ import annotations

from harness.output import extract_json


def test_extract_fenced_json():
    text = "Here is the data:\n```json\n{\"name\": \"alice\", \"age\": 30}\n```\nDone."
    result = extract_json(text)
    assert result == {"name": "alice", "age": 30}


def test_extract_raw_json():
    text = 'Result: {"status": "ok", "value": 42}'
    result = extract_json(text)
    assert result == {"status": "ok", "value": 42}


def test_no_json_returns_none():
    assert extract_json("just plain text") is None


def test_nested_object():
    text = '{"outer": {"inner": "value"}}'
    result = extract_json(text)
    assert result == {"outer": {"inner": "value"}}
