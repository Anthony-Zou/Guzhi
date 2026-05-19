"""Tests for domain.supporting_edges.select_supporting_edges。

挑"共簇里、不和 seed 重复的"补充边,作为 narrate 时的上下文丰富材料。

规则:
- 只看两人的 shared_clusters
- 排除 seed 的 a_entity / b_entity (那两条已经是 prompt 的主线)
- 按 strength 降序 (越强烈越像"心事")
- 标注是 A 还是 B 的边
- 限制 K 条总量 (默认 4)
- 输出顺序: A 的优先 + B 的优先交替 (避免单边压倒)

这是纯函数,domain pure logic,无 IO。
"""
from __future__ import annotations

from domain.models import Cluster, ClusterLevel, Edge, Persona
from domain.supporting_edges import select_supporting_edges, SupportingEdge


def _e(rel: str, entity: str, strength: float, cluster: str | None = "C1") -> Edge:
    return Edge(relation=rel, entity=entity, strength=strength,
                cluster=cluster, evidence=f"原话:{entity}")


def _p(pid: str, name: str, edges: list[Edge]) -> Persona:
    return Persona(id=pid, name=name, gender="", archetype="", edges=tuple(edges))


def _clusters() -> dict[str, Cluster]:
    return {
        "C1": Cluster(id="C1", name="去留之惑", level=ClusterLevel.L3, signal="S_DRIFT"),
        "C2": Cluster(id="C2", name="反效率主义", level=ClusterLevel.L2, signal="S_VALUE"),
        "C9": Cluster(id="C9", name="某偏好", level=ClusterLevel.L1, signal="S_TASTE"),
    }


class TestSelectSupportingEdges:
    def test_returns_only_edges_in_shared_clusters(self):
        a = _p("A", "甲", [
            _e("FEELS_NOW", "回老家", 0.9, "C1"),
            _e("LIKES", "蒙古菜", 0.6, "C9"),  # 共簇里没 C9 -> 应被剔除
        ])
        b = _p("B", "乙", [
            _e("FEELS_NOW", "回老家", 0.8, "C1"),
        ])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=4,
        )
        # C9 不在 shared_clusters,不该出现
        entities = [s.entity for s in out]
        assert "蒙古菜" not in entities

    def test_excludes_seed_entities(self):
        """seed 已经用过的 entity 不再补充。"""
        a = _p("A", "甲", [
            _e("FEELS_NOW", "回老家", 0.9, "C1"),
            _e("DISLIKES", "PPT 文化", 0.7, "C1"),
        ])
        b = _p("B", "乙", [
            _e("FEELS_NOW", "回老家", 0.85, "C1"),
        ])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities={"回老家"}, k=4,
        )
        entities = [s.entity for s in out]
        assert "回老家" not in entities
        assert "PPT 文化" in entities

    def test_sorts_by_strength_descending(self):
        a = _p("A", "甲", [
            _e("FEELS_NOW", "x1", 0.3, "C1"),
            _e("FEELS_NOW", "x2", 0.9, "C1"),
            _e("FEELS_NOW", "x3", 0.6, "C1"),
        ])
        b = _p("B", "乙", [])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=4,
        )
        # 顺序按 strength 降
        strengths = [s.strength for s in out]
        assert strengths == sorted(strengths, reverse=True)

    def test_labels_owner_correctly(self):
        a = _p("A", "甲", [_e("LIKES", "山", 0.8, "C1")])
        b = _p("B", "乙", [_e("LIKES", "海", 0.8, "C1")])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=4,
        )
        by_owner = {s.entity: s.owner for s in out}
        assert by_owner["山"] == "A"
        assert by_owner["海"] == "B"

    def test_k_limits_output(self):
        a = _p("A", "甲", [
            _e("F", f"x{i}", 0.9 - i * 0.05, "C1") for i in range(10)
        ])
        b = _p("B", "乙", [])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=3,
        )
        assert len(out) == 3

    def test_alternates_a_b_to_avoid_dominance(self):
        """同强度时 A 和 B 应当交替出现,不能 A 全占头部。"""
        a = _p("A", "甲", [
            _e("F", "a1", 0.8, "C1"),
            _e("F", "a2", 0.8, "C1"),
            _e("F", "a3", 0.8, "C1"),
        ])
        b = _p("B", "乙", [
            _e("F", "b1", 0.8, "C1"),
            _e("F", "b2", 0.8, "C1"),
        ])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=4,
        )
        owners = [s.owner for s in out]
        # 前 4 条不应该全是 A
        assert owners.count("A") < 4

    def test_empty_inputs_return_empty(self):
        a = _p("A", "甲", [])
        b = _p("B", "乙", [])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=4,
        )
        assert out == []

    def test_supporting_edge_carries_relation_and_evidence(self):
        a = _p("A", "甲", [_e("DISLIKES", "PPT", 0.7, "C1")])
        b = _p("B", "乙", [])
        out = select_supporting_edges(
            a, b, shared_clusters=("C1",), clusters=_clusters(),
            exclude_entities=set(), k=4,
        )
        assert len(out) == 1
        s = out[0]
        assert s.relation == "DISLIKES"
        assert s.evidence == "原话:PPT"
