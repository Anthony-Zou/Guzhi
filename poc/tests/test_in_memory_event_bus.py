"""Tests for adapters.in_memory_event_bus —— 进程内 EventBus 实现。

设计契约 (对应 ports.event_bus.MeetingEventBus):
- publish(event): 入队
- poll(): 取下一个事件,空队列返 None。FIFO 顺序。
- ack(event_id): 标记一个事件"已处理"。
- 未 ack 的事件不会被再次 poll —— 但失败后可显式 requeue。
   (POC 阶段最简,等真上 Kafka 再换语义)

幂等去重:同 event_id 的 publish 第二次应被忽略 —— 这是事件驱动的常见要求。
"""
from __future__ import annotations

import pytest

from adapters.in_memory_event_bus import InMemoryEventBus
from domain.events import MeetingEvent


def _evt(**kw):
    defaults = dict(
        a_id="P1", b_id="P2",
        score=0.2, shared_clusters=("S1",), shared_levels=("L2",),
        tick=0, sim_run_id="r0",
    )
    defaults.update(kw)
    return MeetingEvent(**defaults)


class TestPublishAndPoll:
    def test_empty_poll_returns_none(self):
        bus = InMemoryEventBus()
        assert bus.poll() is None

    def test_publish_then_poll_returns_event(self):
        bus = InMemoryEventBus()
        e = _evt()
        bus.publish(e)
        assert bus.poll() is e

    def test_poll_is_fifo(self):
        bus = InMemoryEventBus()
        e1 = _evt(tick=1)
        e2 = _evt(tick=2)
        e3 = _evt(tick=3)
        bus.publish(e1); bus.publish(e2); bus.publish(e3)
        assert bus.poll() is e1
        assert bus.poll() is e2
        assert bus.poll() is e3
        assert bus.poll() is None

    def test_polled_events_dont_repeat_without_requeue(self):
        bus = InMemoryEventBus()
        e = _evt()
        bus.publish(e)
        bus.poll()
        assert bus.poll() is None  # 不会重发


class TestIdempotentPublish:
    def test_duplicate_event_id_is_ignored_after_ack(self):
        """ack 后,再 publish 同 id 事件应被忽略 —— 幂等保护。"""
        bus = InMemoryEventBus()
        e = _evt()
        bus.publish(e)
        polled = bus.poll()
        bus.ack(polled.event_id)
        # 再 publish 同一个
        bus.publish(e)
        assert bus.poll() is None, "ack 过的事件不该再被处理"

    def test_duplicate_before_ack_also_ignored(self):
        """连续两次 publish 同 id 也只入队一次。"""
        bus = InMemoryEventBus()
        e = _evt()
        bus.publish(e)
        bus.publish(e)
        first = bus.poll()
        assert first is e
        assert bus.poll() is None


class TestRequeue:
    def test_requeue_makes_event_pollable_again(self):
        """worker 处理失败时显式 requeue,事件回到队尾。"""
        bus = InMemoryEventBus()
        e = _evt()
        bus.publish(e)
        bus.poll()
        bus.requeue(e)
        assert bus.poll() is e
