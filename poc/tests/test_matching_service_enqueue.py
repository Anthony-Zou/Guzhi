"""MatchingService.enqueue_narrate —— 把"做匹配 + 推演"从同步阻塞改成
异步事件驱动。

旧的 narrate_match: 同步,阻塞直到 LLM 返回。
新的 enqueue_narrate: 把事件发到 EventBus,立刻返回 event_id。
真正的 narrate 由 NarrateWorker 异步消费。

老接口 (narrate_match) 不删 —— 测试和小镇 demo 仍可用。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.in_memory_event_bus import InMemoryEventBus
from adapters.in_memory_narration_sink import InMemoryNarrationSink
from adapters.json_persona_repository import JsonPersonaRepository
from adapters.stub_narrator import StubNarrator
from app.matching_service import MatchingService
from app.narrate_worker import NarrateWorker


DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class TestEnqueueNarrate:
    def test_enqueue_returns_event_id_without_calling_narrator(self):
        bus = InMemoryEventBus()
        repo = JsonPersonaRepository(DATA_DIR)
        # 故意给一个会爆的 narrator —— 证明 enqueue 不真调
        class _Boom:
            def narrate(self, *a, **kw):
                raise AssertionError("不应该被同步调用!")
        svc = MatchingService(repo, _Boom(), event_bus=bus, sim_run_id="r-test")  # type: ignore[arg-type]

        result = svc.find_matches_for("P1")[0]
        eid = svc.enqueue_narrate(result)

        assert isinstance(eid, str) and len(eid) > 0
        # 队列里有这个事件
        polled = bus.poll()
        assert polled is not None
        assert polled.event_id == eid

    def test_worker_picks_up_and_writes_narration(self):
        """端到端:enqueue → worker.process_one → sink 拿到结果。"""
        bus = InMemoryEventBus()
        sink = InMemoryNarrationSink()
        repo = JsonPersonaRepository(DATA_DIR)
        narrator = StubNarrator()

        svc = MatchingService(repo, narrator, event_bus=bus, sim_run_id="r-e2e")
        worker = NarrateWorker(bus=bus, narrator=narrator, sink=sink, repo=repo)

        # 给 P1 找到最高分匹配 + enqueue
        results = svc.find_matches_for("P1")
        assert results, "P1 应有 matches"
        eid = svc.enqueue_narrate(results[0])

        # sink 现在还是空的
        assert sink.get(eid) is None

        # worker 跑一次
        ok = worker.process_one()
        assert ok is True

        # sink 现在有结果
        out = sink.get(eid)
        assert out is not None and len(out) > 0


class TestEnqueueRequiresBus:
    def test_enqueue_without_bus_raises(self):
        """没注入 bus 就调 enqueue 应该报错 —— 明确告诉调用者缺哪一块。"""
        repo = JsonPersonaRepository(DATA_DIR)
        svc = MatchingService(repo, StubNarrator())  # 没传 bus
        result = svc.find_matches_for("P1")[0]
        import pytest
        with pytest.raises(RuntimeError):
            svc.enqueue_narrate(result)


class TestSyncNarrateStillWorks:
    """同步路径 narrate_match 不该因为加了 enqueue 就坏。"""
    def test_sync_narrate_match_unchanged(self):
        repo = JsonPersonaRepository(DATA_DIR)
        svc = MatchingService(repo, StubNarrator())
        result = svc.find_matches_for("P1")[0]
        out = svc.narrate_match(result)
        assert out and isinstance(out, str)
