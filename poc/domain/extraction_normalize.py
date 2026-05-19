"""domain 层 — 抽取结果归一化。

纯函数，零外部依赖。把 LLM 抽出来的"原始边"洗成可信的 Edge。

为什么需要这一步：
LLM 的输出不可信 —— strength 可能越界、可能引用不存在的簇、
entity 可能是同义改写、可能归错簇、可能缺字段。
normalize_edges 是 KG 的"质检关口"：脏数据进不了图。

归一化规则是领域知识，所以放 domain 层。LLM 调用（adapters）在外面。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain.models import Edge


@dataclass(frozen=True)
class NormalizeContext:
    """归一化所需的上下文。

    valid_clusters:    合法的簇 id 集合
    entity_to_cluster: 已知 entity -> (规范簇 id, 规范 relation)
                       —— 用来纠正 LLM 归错的簇 / relation
    entity_aliases:    同义改写 -> 规范 entity 名
    """
    valid_clusters: set[str]
    entity_to_cluster: dict[str, tuple[str, str]]
    entity_aliases: dict[str, str] = field(default_factory=dict)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def normalize_edges(raw_edges: list[dict],
                    ctx: NormalizeContext) -> list[Edge]:
    """把 LLM 返回的 raw 边列表洗成 Edge 列表。

    处理：
      - 缺字段 -> 跳过
      - strength 越界 -> clamp 到 [0,1]
      - entity 是同义改写 -> 解析成规范名
      - entity 在已知库里 -> 用库纠正 cluster 和 relation
      - entity 不在库里 -> 保留为噪音边（cluster=None）
      - cluster 引用了不存在的簇（且 entity 也未知）-> 丢弃
      - 同一 entity 重复 -> 去重，保留 strength 较高的
    """
    by_entity: dict[str, Edge] = {}

    for raw in raw_edges:
        # 1. 字段完整性
        relation = raw.get("relation")
        entity = raw.get("entity")
        if not relation or not entity:
            continue

        strength = _clamp(float(raw.get("strength", 0.5)))
        cluster = raw.get("cluster")
        evidence = raw.get("evidence", "")

        # 2. 同义改写 -> 规范 entity 名
        entity = ctx.entity_aliases.get(entity, entity)

        # 3. entity 在已知库里：用库纠正 cluster + relation
        if entity in ctx.entity_to_cluster:
            cluster, relation = ctx.entity_to_cluster[entity]
        else:
            # 4. entity 未知：
            #    - 如果 LLM 给的 cluster 不合法，降级为噪音边（cluster=None）
            #    - 如果 LLM 没给 cluster，本来就是噪音边
            if cluster is not None and cluster not in ctx.valid_clusters:
                cluster = None

        edge = Edge(
            relation=relation,
            entity=entity,
            strength=strength,
            cluster=cluster,
            evidence=evidence,
        )

        # 5. 去重：同 entity 保留 strength 较高的
        existing = by_entity.get(entity)
        if existing is None or edge.strength > existing.strength:
            by_entity[entity] = edge

    # 按 entity 名排序，保证确定性
    return [by_entity[k] for k in sorted(by_entity)]
