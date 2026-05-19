"""domain 层 — 值对象。

严格六边形架构：domain 是最内层，零外部依赖，不 import 任何其他层。
这里只有不可变的值对象，没有 IO、没有框架、没有 AI。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ClusterLevel(Enum):
    """语义簇的深度等级。匹配不只看信号强度，还看深度。"""
    L1 = "L1"  # 偏好 / 品味 / 风格
    L2 = "L2"  # 价值观 / 世界观
    L3 = "L3"  # 存在性议题 —— 人最深层的东西


# 深度等级 -> 总分加权乘子
_DEPTH_MULTIPLIER = {
    ClusterLevel.L1: 0.7,
    ClusterLevel.L2: 1.0,
    ClusterLevel.L3: 1.3,
}


@dataclass(frozen=True)
class Edge:
    """一条 KG 边：(某人) -[relation]-> (entity)。

    frozen=True 保证不可变 —— 值对象不应被修改。
    """
    relation: str          # LIKES / DISLIKES / BELIEVES / EXPERIENCED / FEELS_NOW / SPEAKS_AS
    entity: str            # 归一化后的实体名
    strength: float        # 0.0 - 1.0
    cluster: str | None    # 所属语义簇 id，没有则 None
    evidence: str          # 自述文本中支持这条边的原话

    def __post_init__(self) -> None:
        if not (0.0 <= self.strength <= 1.0):
            raise ValueError(
                f"strength 必须在 [0,1]，得到 {self.strength}"
            )


@dataclass(frozen=True)
class Cluster:
    """语义簇定义。"""
    id: str
    name: str
    level: ClusterLevel
    signal: str  # 该簇命中归到哪类信号

    def depth_multiplier(self) -> float:
        return _DEPTH_MULTIPLIER[self.level]


@dataclass(frozen=True)
class Persona:
    """一个人 = 一组边的集合（一张子图）。

    name / gender / archetype 是展示信息，不参与匹配。
    匹配只看 edges（KG 子图）—— 这是 KG-First 的核心：
    性别、名字都不影响"谁和谁合"。
    """
    id: str
    name: str
    edges: tuple[Edge, ...] = field(default_factory=tuple)
    gender: str = ""        # "male" / "female" / ""（手工数据集不填）
    archetype: str = ""     # 特质画像，如 "去留之间·低谷里的人"

    def __post_init__(self) -> None:
        # 允许传 list，内部统一存 tuple（不可变）
        if not isinstance(self.edges, tuple):
            object.__setattr__(self, "edges", tuple(self.edges))

    def edges_in_cluster(self, cluster_id: str) -> list[Edge]:
        """返回这个人在指定语义簇里的所有边。"""
        return [e for e in self.edges if e.cluster == cluster_id]

    def clusters_present(self) -> set[str]:
        """返回这个人涉及的所有簇 id（用于零共簇闸）。"""
        return {e.cluster for e in self.edges if e.cluster is not None}

    def style_tags(self) -> set[str]:
        """返回 SPEAKS_AS 的标签集合。"""
        return {e.entity for e in self.edges if e.relation == "SPEAKS_AS"}
