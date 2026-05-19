"""域层 —— 选出"补充边"以丰富 narrate prompt。

故知 P0.3 的核心:把 RAG 收窄做成"按 call point 分层 enrich"。
低档 (Haiku) 不 enrich,保持 ~300 token;
高档 (Sonnet / Opus) enrich K 条,让笔触更细腻。

这个函数本身只决定"挑哪些边",不决定"用还是不用 enrich"。
后者是 RoutedNarrator 的策略。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from domain.models import Cluster, Persona


@dataclass(frozen=True)
class SupportingEdge:
    """一条补充边,带"是谁的"标签 (A/B),供 prompt 拼装时区分。"""
    owner: str        # "A" 或 "B"
    relation: str
    entity: str
    strength: float
    cluster: str      # 一定不为 None (已过滤共簇)
    evidence: str


def _person_edges_in_clusters(
    p: Persona,
    shared_clusters: set[str],
    exclude_entities: set[str],
) -> list[SupportingEdge]:
    """从一个人的 edges 里挑出"在共簇里、entity 不在排除集"的。
    返回时 owner 暂不填,由调用方填。"""
    out: list[SupportingEdge] = []
    for e in p.edges:
        if e.cluster is None or e.cluster not in shared_clusters:
            continue
        if e.entity in exclude_entities:
            continue
        out.append(SupportingEdge(
            owner="",  # caller 填
            relation=e.relation,
            entity=e.entity,
            strength=e.strength,
            cluster=e.cluster,
            evidence=e.evidence,
        ))
    return out


def _stamp_owner(edges: list[SupportingEdge], owner: str) -> list[SupportingEdge]:
    return [SupportingEdge(
        owner=owner, relation=e.relation, entity=e.entity,
        strength=e.strength, cluster=e.cluster, evidence=e.evidence,
    ) for e in edges]


def _interleave(a_list: list[SupportingEdge],
                b_list: list[SupportingEdge]) -> list[SupportingEdge]:
    """A、B 交替,避免单边压头。各自先按 strength 降序。"""
    a_sorted = sorted(a_list, key=lambda e: -e.strength)
    b_sorted = sorted(b_list, key=lambda e: -e.strength)
    out: list[SupportingEdge] = []
    i = j = 0
    while i < len(a_sorted) or j < len(b_sorted):
        if i < len(a_sorted):
            out.append(a_sorted[i]); i += 1
        if j < len(b_sorted):
            out.append(b_sorted[j]); j += 1
    return out


def select_supporting_edges(
    a: Persona, b: Persona, *,
    shared_clusters: Iterable[str],
    clusters: dict[str, Cluster],   # 接收 catalog 以备后续按 level 加权,当前未用
    exclude_entities: set[str],
    k: int = 4,
) -> list[SupportingEdge]:
    """挑 K 条补充边。

    步骤:
      1. 各取自人在共簇里、不在排除集的 edges
      2. 各自按 strength 降序
      3. A/B 交替合并 (避免单边压头)
      4. 截到 K 条
    """
    del clusters  # 未来想按 L3 > L2 > L1 加权时会用,当前不用
    shared = set(shared_clusters)

    a_edges = _stamp_owner(
        _person_edges_in_clusters(a, shared, exclude_entities), "A"
    )
    b_edges = _stamp_owner(
        _person_edges_in_clusters(b, shared, exclude_entities), "B"
    )

    interleaved = _interleave(a_edges, b_edges)
    return interleaved[:k]
