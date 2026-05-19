"""端口 —— NarrationSink。

"narrate 完了把结果放哪"的抽象。
POC 用 in-memory,生产可换 DB / 用户收件箱 / 等等。

worker 不应该知道 sink 的具体存储方式 —— 它只 save。
读取方 (UI / 通知服务) 也只知道这个端口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class NarrationSink(ABC):
    @abstractmethod
    def save(self, event_id: str, narration: str) -> None:
        ...

    @abstractmethod
    def get(self, event_id: str) -> str | None:
        ...

    @abstractmethod
    def all_ids(self) -> list[str]:
        ...
