"""adapter —— InMemoryNarrationSink。

进程内 dict 实现 NarrationSink。POC 用。
"""
from __future__ import annotations

from ports.narration_sink import NarrationSink


class InMemoryNarrationSink(NarrationSink):
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def save(self, event_id: str, narration: str) -> None:
        self._store[event_id] = narration

    def get(self, event_id: str) -> str | None:
        return self._store.get(event_id)

    def all_ids(self) -> list[str]:
        return list(self._store.keys())
