"""Tests for adapters.in_memory_narration_sink。

Sink 是"narrate 完了把结果放哪"的抽象。
端口契约: save(event_id, narration: str) -> None,get(event_id) -> str | None。
"""
from __future__ import annotations

from adapters.in_memory_narration_sink import InMemoryNarrationSink


class TestSink:
    def test_save_then_get(self):
        sink = InMemoryNarrationSink()
        sink.save("evt-1", "他们在面馆拼了桌。")
        assert sink.get("evt-1") == "他们在面馆拼了桌。"

    def test_missing_returns_none(self):
        sink = InMemoryNarrationSink()
        assert sink.get("nope") is None

    def test_overwrite_latest_wins(self):
        sink = InMemoryNarrationSink()
        sink.save("evt-1", "v1")
        sink.save("evt-1", "v2")
        assert sink.get("evt-1") == "v2"

    def test_all_ids_returns_what_was_saved(self):
        sink = InMemoryNarrationSink()
        sink.save("a", "x")
        sink.save("b", "y")
        assert set(sink.all_ids()) == {"a", "b"}
