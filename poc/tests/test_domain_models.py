"""TDD — domain 层值对象测试。先写测试，再写实现。

domain 层规则：纯值对象，零外部依赖，不 import 任何其他层。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona, Cluster, ClusterLevel


def test_edge_is_immutable_value_object():
    e = Edge(relation="LIKES", entity="黑泽明", strength=0.95,
             cluster="C7", evidence="痴迷黑泽明")
    assert e.relation == "LIKES"
    assert e.entity == "黑泽明"
    assert e.strength == 0.95
    assert e.cluster == "C7"
    # 不可变
    try:
        e.strength = 0.1
        assert False, "Edge 应该是不可变的"
    except (AttributeError, Exception):
        pass


def test_edge_strength_must_be_in_range():
    try:
        Edge(relation="LIKES", entity="x", strength=1.5, cluster=None, evidence="")
        assert False, "strength > 1.0 应该被拒绝"
    except ValueError:
        pass
    try:
        Edge(relation="LIKES", entity="x", strength=-0.1, cluster=None, evidence="")
        assert False, "strength < 0 应该被拒绝"
    except ValueError:
        pass


def test_persona_holds_edges():
    edges = [
        Edge("LIKES", "黑泽明", 0.95, "C7", "x"),
        Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "y"),
    ]
    p = Persona(id="P1", name="林知", edges=edges)
    assert p.id == "P1"
    assert len(p.edges) == 2


def test_persona_edges_in_cluster():
    """Persona 能返回它在某个簇里的所有边——匹配算法要用。"""
    edges = [
        Edge("LIKES", "黑泽明", 0.95, "C7", "x"),
        Edge("BELIEVES", "野心会反噬人", 0.8, "C7", "y"),
        Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "z"),
        Edge("EXPERIENCED", "北漂六年", 0.7, None, "w"),
    ]
    p = Persona(id="P1", name="林知", edges=edges)
    c7 = p.edges_in_cluster("C7")
    assert len(c7) == 2
    assert p.edges_in_cluster("C1") == [p.edges[2]]
    assert p.edges_in_cluster("C99") == []


def test_persona_clusters_present():
    """Persona 能返回它涉及的所有簇 id 集合——零共簇闸要用。"""
    edges = [
        Edge("LIKES", "黑泽明", 0.95, "C7", "x"),
        Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "z"),
        Edge("EXPERIENCED", "北漂六年", 0.7, None, "w"),
    ]
    p = Persona(id="P1", name="林知", edges=edges)
    assert p.clusters_present() == {"C7", "C1"}


def test_persona_style_tags():
    """Persona 能返回 SPEAKS_AS 的标签集合——风格匹配要用。"""
    edges = [
        Edge("SPEAKS_AS", "冷面笑匠", 0.85, None, "x"),
        Edge("SPEAKS_AS", "短句", 0.6, None, "y"),
        Edge("LIKES", "黑泽明", 0.95, "C7", "z"),
    ]
    p = Persona(id="P1", name="林知", edges=edges)
    assert p.style_tags() == {"冷面笑匠", "短句"}


def test_cluster_level():
    c = Cluster(id="C1", name="去留之惑", level=ClusterLevel.L3,
                signal="feeling_resonance")
    assert c.level == ClusterLevel.L3
    assert c.depth_multiplier() == 1.3

    c2 = Cluster(id="C2", name="反效率主义", level=ClusterLevel.L2,
                 signal="belief_alignment")
    assert c2.depth_multiplier() == 1.0

    c3 = Cluster(id="C3", name="反正能量表演", level=ClusterLevel.L1,
                 signal="shared_aversion")
    assert c3.depth_multiplier() == 0.7
