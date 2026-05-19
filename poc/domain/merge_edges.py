"""域层 —— 合并 KG 边。

弱养成的核心:用户每次投喂会抽出一组新边,合到已有 KG。
合并规则在领域层,不在 IO 层 —— 因为这是业务知识 (什么算"同一条边"、
强度怎么调和、对立怎么处理),不是基础设施。

规则总览(对照测试):
1. (relation, entity) 相同 -> max(strength),保留更长的 evidence
2. 同 entity 不同 relation (LIKES X / DISLIKES X) -> 都保留
3. 完全新 -> append
4. 输出按 (relation, entity, cluster) 字典序 -> 幂等 + 测试友好
"""
from __future__ import annotations

from typing import Iterable, Sequence

from domain.models import Edge


def _key(e: Edge) -> tuple[str, str]:
    """同 (relation, entity) 视为同一条边。cluster 不参与 key —— 如果归簇
    变了,以"内容是什么"为准而不是"它在哪个簇里"。"""
    return (e.relation, e.entity)


def _merge_two(old: Edge, new: Edge) -> Edge:
    """同 key 的两条 -> 一条:max strength + 更长 evidence + new 的 cluster
    (允许 cluster 修正,因为 catalog 可能更新)。"""
    strength = max(old.strength, new.strength)
    evidence = (
        new.evidence if len(new.evidence) > len(old.evidence)
        else old.evidence
    )
    cluster = new.cluster or old.cluster
    return Edge(
        relation=old.relation,
        entity=old.entity,
        strength=strength,
        cluster=cluster,
        evidence=evidence,
    )


def merge_edges(*, existing: Sequence[Edge],
                new: Iterable[Edge]) -> tuple[Edge, ...]:
    """合并 existing + new 成一组 edges。

    保证:
    - 不修改 existing (它是 tuple,本来就 immutable;但也不构造别名)
    - 输出顺序由 (relation, entity, cluster) 字典序确定 (deterministic)
    """
    by_key: dict[tuple[str, str], Edge] = {}
    for e in existing:
        by_key[_key(e)] = e
    for e in new:
        k = _key(e)
        if k in by_key:
            by_key[k] = _merge_two(by_key[k], e)
        else:
            by_key[k] = e

    merged = list(by_key.values())
    merged.sort(key=lambda e: (e.relation, e.entity, e.cluster or ""))
    return tuple(merged)
