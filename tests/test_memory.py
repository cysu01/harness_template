"""Tests for Module 3 — Memory System."""

from __future__ import annotations

from harness.memory import InMemoryVectorMemory, ShortTermMemory


def test_short_term_append_and_history():
    mem = ShortTermMemory("test-session")
    mem.append({"role": "user", "content": "hi"})
    mem.append({"role": "assistant", "content": "hello"})
    assert len(mem) == 2
    assert mem.history()[0]["content"] == "hi"


def test_short_term_max_messages_trims():
    mem = ShortTermMemory("trim-test", max_messages=3)
    for i in range(5):
        mem.append({"role": "user", "content": str(i)})
    history = mem.history()
    assert len(history) == 3
    assert history[0]["content"] == "2"
    assert history[-1]["content"] == "4"


def test_long_term_search_returns_closest_match():
    # Toy embedding: count of vowels per word as 5-dim vector.
    def embed(text: str) -> list[float]:
        vowels = "aeiou"
        return [float(sum(1 for c in text.lower() if c == v)) for v in vowels]

    store = InMemoryVectorMemory(embed)
    store.add("apple")
    store.add("banana")
    store.add("orange")

    results = store.search("aaple", k=1)
    assert len(results) == 1
    assert results[0].text == "apple"
