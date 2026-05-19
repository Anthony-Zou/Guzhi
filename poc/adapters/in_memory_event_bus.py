"""adapter —— InMemoryEventBus。

进程内 FIFO 队列实现 MeetingEventBus 端口。
POC / 单进程跑足够;规模化时换 RedisEventBus / KafkaEventBus,
caller (composition root) 不动。

幂等保证:
- 事件 id 进过 _seen,无论 ack 与否,再 publish 都跳过。
- 这是给"上游 simulator 不知道自己 publish 过"的兜底。
- 失败回退用 requeue —— 显式语义,不靠 publish 重发。
"""
from __future__ import annotations

from collections import deque

from domain.events import MeetingEvent
from ports.event_bus import MeetingEventBus


class InMemoryEventBus(MeetingEventBus):
    def __init__(self) -> None:
        self._queue: deque[MeetingEvent] = deque()
        self._seen: set[str] = set()        # 已入过队 (或处理过) 的 event_id

    def publish(self, event: MeetingEvent) -> None:
        if event.event_id in self._seen:
            return                          # 幂等忽略
        self._seen.add(event.event_id)
        self._queue.append(event)

    def poll(self) -> MeetingEvent | None:
        if not self._queue:
            return None
        return self._queue.popleft()

    def ack(self, event_id: str) -> None:
        # 当前 in-memory 实现没有 inflight 列表 —— ack 只是个 noop 信号。
        # 等真上 Kafka 再实现"未 ack 超时回吐"的语义。
        # 保留 event_id 在 _seen 里:同 id 不会被重新 publish。
        del event_id

    def requeue(self, event: MeetingEvent) -> None:
        # 失败回退:绕过 _seen 检查,直接回到队尾
        self._queue.append(event)
