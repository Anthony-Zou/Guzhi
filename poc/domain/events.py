"""域层 —— 事件 (domain events)。

MeetingEvent: 一次"两人在小镇相遇"的领域事件。
不可变,自带稳定 id (基于内容哈希) —— 允许 worker 幂等消费。

故知的事件驱动设计:
  Town 状态机 → 产出 MeetingEvent → 发到 EventBus → NarrateWorker
  消费 → narrate → 写回 sink。

事件本身不依赖任何基础设施 (queue/db/network) —— 那是 adapter 的事。
事件只是数据 + 不变量。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MeetingEvent:
    """两人相遇的领域事件。

    携带 narrate 需要的全部决策信息,这样下游 worker 不必再访问 repo
    或重跑 match。如果未来事件源换成 Kafka 之类,事件会被序列化 ——
    所有字段都应该是值类型 (字符串/数字/元组),不放对象引用。
    """
    a_id: str
    b_id: str
    score: float
    shared_clusters: tuple[str, ...]
    shared_levels: tuple[str, ...]   # 与 shared_clusters 一一对应的 level 列表
    tick: int
    sim_run_id: str                  # 哪一轮模拟产生的 —— 让幂等去重有依据

    # 派生字段:稳定 event_id (基于内容)
    event_id: str = field(init=False)

    def __post_init__(self) -> None:
        if self.a_id == self.b_id:
            raise ValueError(f"事件不能自指: a_id == b_id == {self.a_id}")
        if self.score < 0:
            raise ValueError(f"score 必须 >= 0,得到 {self.score}")
        # 计算稳定 id
        key = f"{self.sim_run_id}|{self.tick}|{self.a_id}|{self.b_id}|{self.score}"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        # frozen dataclass 不能直接赋值,绕过去
        object.__setattr__(self, "event_id", digest)
