"""Tests for domain.merge_edges.merge_edges。

把"新抽到的边"合进"已有 KG"。纯函数。

规则:
1. (relation, entity) 完全重复 -> strength 取 max (不累加,避免 > 1)
2. 同 entity / 不同 relation (例如 LIKES X 后来出现 DISLIKES X) -> 两条都保留
   (用户真的可能改主意,让下游看到对立。merge 不替用户做心理判断)
3. 完全新边 -> 直接 append
4. evidence: 同 (relation, entity) 重复时保留更长的那条 (信息量更大)
5. 结果保持稳定排序 (按 (relation, entity, cluster) 字典序) —— 这样 merge
   是幂等的、deterministic 的、对回归测试友好
"""
from __future__ import annotations

from domain.models import Edge
from domain.merge_edges import merge_edges


def _e(rel: str, entity: str, strength: float,
       cluster: str | None = "C1", evidence: str = "原话") -> Edge:
    return Edge(relation=rel, entity=entity, strength=strength,
                cluster=cluster, evidence=evidence)


class TestMergeBasics:
    def test_empty_existing_returns_new(self):
        new = [_e("LIKES", "山", 0.7)]
        out = merge_edges(existing=(), new=new)
        assert len(out) == 1
        assert out[0].entity == "山"

    def test_empty_new_returns_existing(self):
        existing = (_e("LIKES", "海", 0.8),)
        out = merge_edges(existing=existing, new=[])
        assert list(out) == list(existing)

    def test_disjoint_appends(self):
        existing = (_e("LIKES", "山", 0.7),)
        new = [_e("LIKES", "海", 0.6)]
        out = merge_edges(existing=existing, new=new)
        entities = {e.entity for e in out}
        assert entities == {"山", "海"}


class TestDuplicateRelationEntity:
    def test_same_rel_entity_keeps_max_strength(self):
        existing = (_e("LIKES", "山", 0.5),)
        new = [_e("LIKES", "山", 0.9)]
        out = merge_edges(existing=existing, new=new)
        assert len(out) == 1
        assert out[0].strength == 0.9

    def test_same_rel_entity_keeps_longer_evidence(self):
        existing = (_e("LIKES", "山", 0.5, evidence="短"),)
        new = [_e("LIKES", "山", 0.5, evidence="更长的原话证据")]
        out = merge_edges(existing=existing, new=new)
        assert len(out) == 1
        assert out[0].evidence == "更长的原话证据"

    def test_lower_new_strength_does_not_downgrade(self):
        """新边强度比已有低时,保留高的 —— '我确认过的不该被弱化'。"""
        existing = (_e("LIKES", "山", 0.9),)
        new = [_e("LIKES", "山", 0.3)]
        out = merge_edges(existing=existing, new=new)
        assert out[0].strength == 0.9


class TestConflictingRelations:
    def test_likes_then_dislikes_same_entity_both_kept(self):
        """LIKES X 后又 DISLIKES X —— 都保留,让下游看到对立。"""
        existing = (_e("LIKES", "团建", 0.6),)
        new = [_e("DISLIKES", "团建", 0.8)]
        out = merge_edges(existing=existing, new=new)
        rels = {(e.relation, e.entity) for e in out}
        assert ("LIKES", "团建") in rels
        assert ("DISLIKES", "团建") in rels


class TestDeterministicOrdering:
    def test_output_order_is_stable(self):
        """同一输入,无论顺序,输出顺序确定。"""
        a = [_e("LIKES", "山", 0.7), _e("DISLIKES", "PPT", 0.8)]
        b = [_e("DISLIKES", "PPT", 0.8), _e("LIKES", "山", 0.7)]
        out_a = merge_edges(existing=(), new=a)
        out_b = merge_edges(existing=(), new=b)
        assert list(out_a) == list(out_b)


class TestImmutable:
    def test_does_not_mutate_existing(self):
        existing = (_e("LIKES", "山", 0.5),)
        original = list(existing)
        merge_edges(existing=existing, new=[_e("LIKES", "山", 0.9)])
        assert list(existing) == original  # 还原不动
