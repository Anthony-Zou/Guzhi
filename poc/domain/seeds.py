"""domain 层 — 故事种子提取。

纯函数，零外部依赖。从匹配上的两个人里挖出"可叙事的素材"。
这些种子是后面 AI 推演的唯一输入——AI 不拿两个人的完整资料，只拿种子。
设计文档第 6 节。
"""
from __future__ import annotations

from dataclasses import dataclass

from domain.models import Persona, Cluster, ClusterLevel


@dataclass(frozen=True)
class StorySeed:
    """一颗故事种子。AI 推演的输入单位。"""
    seed_type: str          # "SHARED_CLUSTER" | "CREATIVE_TENSION"
    cluster: str            # 来自哪个语义簇
    a_entity: str
    b_entity: str
    a_evidence: str         # A 的原话——AI 写对话时可引用，但不能编造之外的
    b_evidence: str
    weight: float           # 故事感强度，用于排序


# 种子加权乘子（设计文档 6.2）
_TENSION_BONUS = 1.2
_L3_BONUS = 1.3


def extract_seeds(a: Persona, b: Persona,
                  shared_clusters: set[str],
                  clusters: dict[str, Cluster],
                  tension_pairs: list[tuple[str, str, str]]) -> list[StorySeed]:
    """从两个匹配上的人里提取故事种子，按 weight 降序返回。

    纯图运算：扫两张子图，按规则摘出边对。
    """
    seeds: list[StorySeed] = []

    for cid in shared_clusters:
        cluster = clusters.get(cid)
        if cluster is None:
            continue
        a_edges = a.edges_in_cluster(cid)
        b_edges = b.edges_in_cluster(cid)
        if not a_edges or not b_edges:
            continue

        # 取双方在该簇内最强的边组成一颗 SHARED_CLUSTER 种子
        ea = max(a_edges, key=lambda e: e.strength)
        eb = max(b_edges, key=lambda e: e.strength)
        base_weight = ea.strength * eb.strength
        if cluster.level == ClusterLevel.L3:
            base_weight *= _L3_BONUS

        seeds.append(StorySeed(
            seed_type="SHARED_CLUSTER",
            cluster=cid,
            a_entity=ea.entity,
            b_entity=eb.entity,
            a_evidence=ea.evidence,
            b_evidence=eb.evidence,
            weight=round(base_weight, 4),
        ))

    # CREATIVE_TENSION 种子：簇内对立
    for cluster_id, ent_x, ent_y in tension_pairs:
        if cluster_id not in shared_clusters:
            continue
        a_edges = {e.entity: e for e in a.edges_in_cluster(cluster_id)}
        b_edges = {e.entity: e for e in b.edges_in_cluster(cluster_id)}

        pair = None
        if ent_x in a_edges and ent_y in b_edges:
            pair = (a_edges[ent_x], b_edges[ent_y])
        elif ent_y in a_edges and ent_x in b_edges:
            pair = (a_edges[ent_y], b_edges[ent_x])
        if pair is None:
            continue

        ea, eb = pair
        seeds.append(StorySeed(
            seed_type="CREATIVE_TENSION",
            cluster=cluster_id,
            a_entity=ea.entity,
            b_entity=eb.entity,
            a_evidence=ea.evidence,
            b_evidence=eb.evidence,
            weight=round(ea.strength * eb.strength * _TENSION_BONUS, 4),
        ))

    seeds.sort(key=lambda s: s.weight, reverse=True)
    return seeds
