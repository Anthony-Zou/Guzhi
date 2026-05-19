"""app 层 —— NarrateWorker。

事件驱动架构的消费端。住 app 层因为它编排 (orchestrates):
  bus.poll → repo.get → extract_seeds → classify_meeting →
  narrator.narrate(call_point=...) → sink.save → bus.ack

worker 依赖端口 (bus / narrator / sink / repo),不依赖具体 adapter。
所以单元测试可以注入任意组合 (in-memory bus + stub narrator + ...)。
"""
from __future__ import annotations

from domain.events import MeetingEvent
from domain.matching import MatchResult
from domain.meeting_classifier import classify_meeting
from domain.seeds import extract_seeds
from ports.event_bus import MeetingEventBus
from ports.narration_sink import NarrationSink
from ports.narrator import Narrator
from ports.persona_repository import PersonaRepository


class NarrateWorker:
    def __init__(self,
                 bus: MeetingEventBus,
                 narrator: Narrator,
                 sink: NarrationSink,
                 repo: PersonaRepository) -> None:
        self._bus = bus
        self._narrator = narrator
        self._sink = sink
        self._repo = repo
        # 簇定义 / tension 表一次性加载,复用
        self._clusters = repo.clusters()
        self._tension = repo.tension_pairs()

    def process_one(self) -> bool:
        """处理一个事件。
        返回 True: 成功处理 (已 ack + sink 已写)
        返回 False: 队列空 或 处理失败 (已 requeue,sink 未写)
        """
        event = self._bus.poll()
        if event is None:
            return False
        try:
            narration = self._narrate_for(event)
        except Exception:
            # 失败:回队,留给下次 (或别的 worker) 试。不 ack。
            self._bus.requeue(event)
            return False

        self._sink.save(event.event_id, narration)
        self._bus.ack(event.event_id)
        return True

    def run_until_empty(self) -> int:
        """连续消费直到队列空。返回成功处理的事件数。

        注:如果有 requeue,run_until_empty 会无限循环;
        当前实现里 process_one 在 requeue 后返回 False,所以
        for 一个总是失败的事件,函数会立刻退出。
        生产环境的 worker loop 需要更细的策略 (限流/重试上限),
        现在不做。
        """
        processed = 0
        while True:
            ok = self._bus.poll()
            if ok is None:
                break
            # 把事件放回再用 process_one (它会再 poll)
            # —— 不,这样会撞 _seen 的幂等。直接处理这个 event。
            try:
                narration = self._narrate_for(ok)
            except Exception:
                self._bus.requeue(ok)
                break
            self._sink.save(ok.event_id, narration)
            self._bus.ack(ok.event_id)
            processed += 1
        return processed

    def _narrate_for(self, event: MeetingEvent) -> str:
        """事件 → narration 字符串。提了出来给 process_one 和 run_until_empty 共用。"""
        a = self._repo.get(event.a_id)
        b = self._repo.get(event.b_id)
        seeds = extract_seeds(
            a, b, set(event.shared_clusters),
            self._clusters, self._tension,
        )
        if not seeds:
            return "（无可用故事种子）"
        call_point = classify_meeting(event.score, list(event.shared_levels))
        return self._narrator.narrate(
            seeds[0], a, b,
            call_point=call_point,
            shared_clusters=event.shared_clusters,
        )
