"""Tests for app.narrate_worker.NarrateWorker。

worker 是事件驱动架构的消费端:
  bus.poll() → 解析事件 → repo.get(两人) → extract_seeds →
  classify_meeting → narrator.narrate(call_point=...) → sink.save → bus.ack

行为契约:
  - process_one() 处理一个事件,成功返 True,空队列返 False
  - 失败 (narrate 抛异常) -> requeue,不 ack -> 返回 False (这次没"成功")
  - 整套 narrate 调用走的是 call_point (路由) 路径
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from adapters.fake_llm import FakeLLM
from adapters.in_memory_event_bus import InMemoryEventBus
from adapters.in_memory_narration_sink import InMemoryNarrationSink
from adapters.json_persona_repository import JsonPersonaRepository
from adapters.routed_narrator import RoutedNarrator
from adapters.stub_narrator import StubNarrator
from adapters.tiered_llm_factory import TieredLLMFactory
from app.narrate_worker import NarrateWorker
from domain.events import MeetingEvent
from domain.routing import (
    CallPoint,
    DEFAULT_ROUTING,
    LLMRouter,
    ModelTier,
)


import os
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _evt(a="P1", b="P2", score=0.25, clusters=("C1",), levels=("L3",),
         tick=0, run="r0"):
    """C1 = "去留之惑" L3, 是 8 人集里 P1 和 P2 真实共享的簇。"""
    return MeetingEvent(
        a_id=a, b_id=b, score=score,
        shared_clusters=clusters, shared_levels=levels,
        tick=tick, sim_run_id=run,
    )


def _worker(narrator, bus=None, sink=None):
    repo = JsonPersonaRepository(DATA_DIR)
    bus = bus or InMemoryEventBus()
    sink = sink or InMemoryNarrationSink()
    return NarrateWorker(
        bus=bus, narrator=narrator, sink=sink,
        repo=repo,
    ), bus, sink


class TestProcessOne:
    def test_empty_queue_returns_false(self):
        worker, _, _ = _worker(StubNarrator())
        assert worker.process_one() is False

    def test_processes_event_and_writes_to_sink(self):
        narrator = StubNarrator()
        worker, bus, sink = _worker(narrator)
        e = _evt()
        bus.publish(e)

        ok = worker.process_one()
        assert ok is True

        # sink 写了
        out = sink.get(e.event_id)
        assert out is not None
        # 拿真实人名做断言。8 人集 P1/P2 = 林知/周临 (不写死名字以防数据改名)
        a_name = JsonPersonaRepository(DATA_DIR).get("P1").name
        assert a_name in out
        # 队列空了
        assert bus.poll() is None

    def test_uses_call_point_routing(self):
        """高分 L3 相遇 -> RoutedNarrator -> Opus FakeLLM。"""
        haiku = FakeLLM(canned_response="haiku")
        sonnet = FakeLLM(canned_response="sonnet")
        opus = FakeLLM(canned_response="opus")
        router = LLMRouter(DEFAULT_ROUTING)
        factory = TieredLLMFactory({
            ModelTier.HAIKU: haiku,
            ModelTier.SONNET: sonnet,
            ModelTier.OPUS: opus,
        })
        narrator = RoutedNarrator(router=router, factory=factory)

        worker, bus, sink = _worker(narrator)
        # 高分 + L3 -> L3_PEAK_MEETING_NARRATE -> Opus
        e = _evt(score=0.40, levels=("L3",))
        bus.publish(e)
        worker.process_one()

        assert sink.get(e.event_id) == "opus"
        assert opus.call_count == 1


class TestFailureHandling:
    def test_narrator_failure_requeues_and_does_not_ack(self):
        """narrate 抛异常 -> 事件 requeue,sink 不写。"""
        class _Boom:
            def narrate(self, *a, **kw):
                raise RuntimeError("boom")
        worker, bus, sink = _worker(_Boom())  # type: ignore[arg-type]
        e = _evt()
        bus.publish(e)

        ok = worker.process_one()
        assert ok is False
        # sink 没写
        assert sink.get(e.event_id) is None
        # 事件回到队列里
        assert bus.poll() is e


class TestRunUntilEmpty:
    def test_drains_queue(self):
        worker, bus, sink = _worker(StubNarrator())
        e1 = _evt(tick=1)
        e2 = _evt(tick=2)
        bus.publish(e1); bus.publish(e2)

        processed = worker.run_until_empty()
        assert processed == 2
        assert sink.get(e1.event_id) is not None
        assert sink.get(e2.event_id) is not None


class TestNoSeedFallback:
    def test_event_with_empty_clusters_writes_fallback_text(self):
        """空共簇 -> extract_seeds 返空 -> sink 写一段标记文本而非崩。"""
        # 用 8 人集里两个真实人物,但事件里 shared_clusters 故意填空
        worker, bus, sink = _worker(StubNarrator())
        e = MeetingEvent(
            a_id="P1", b_id="P2", score=0.05,
            shared_clusters=(), shared_levels=(),
            tick=0, sim_run_id="r0",
        )
        bus.publish(e)
        ok = worker.process_one()
        assert ok is True
        out = sink.get(e.event_id)
        assert out is not None
        # 应该有个清晰的"无种子"标记,而不是 stub 模板
        assert "种子" in out or "无" in out
