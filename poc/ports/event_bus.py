"""端口 —— MeetingEventBus。

抽象"发布相遇事件 / 消费"。这一层不应该知道任何具体 queue 实现。

最小契约:
  - publish(event)
  - poll() -> event | None
  - ack(event_id)         标记成功消费
  - requeue(event)        重新入队 (失败回退)

幂等性: 同 event_id 被 publish 多次,只入队一次 (在没被 requeue 的前提下)。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.events import MeetingEvent


class MeetingEventBus(ABC):
    @abstractmethod
    def publish(self, event: MeetingEvent) -> None:
        ...

    @abstractmethod
    def poll(self) -> MeetingEvent | None:
        ...

    @abstractmethod
    def ack(self, event_id: str) -> None:
        ...

    @abstractmethod
    def requeue(self, event: MeetingEvent) -> None:
        ...
