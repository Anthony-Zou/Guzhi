"""TDD — domain 层故事种子提取测试。

故事种子 = 从匹配结果里挖出的、可叙事的素材。纯图运算，零 AI。
设计文档第 6 节。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona, Cluster, ClusterLevel
from domain.seeds import extract_seeds, StorySeed

CLUSTERS = {
    "C1": Cluster("C1", "去留之惑", ClusterLevel.L3, "feeling_resonance"),
    "C7": Cluster("C7", "电影品味", ClusterLevel.L1, "shared_passion"),
}
TENSION_PAIRS = [("C7", "野心会反噬人", "乱是关于宽恕")]


def _persona(pid, *edges):
    return Persona(id=pid, name=pid, edges=tuple(edges))


def test_extract_shared_cluster_seed():
    """两人共享一个簇 -> 提取出一颗该簇的种子，带双方的 evidence。"""
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "答不上来留下的理由"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.85, "C1", "常想留下还是离开"))
    seeds = extract_seeds(a, b, {"C1"}, CLUSTERS, TENSION_PAIRS)
    assert len(seeds) >= 1
    s = seeds[0]
    assert s.cluster == "C1"
    assert s.a_evidence == "答不上来留下的理由"
    assert s.b_evidence == "常想留下还是离开"


def test_tension_seed_is_detected():
    """簇内对立 -> 提取出 CREATIVE_TENSION 种子。"""
    a = _persona("A", Edge("BELIEVES", "野心会反噬人", 0.8, "C7", "野心反噬"))
    b = _persona("B", Edge("BELIEVES", "乱是关于宽恕", 0.8, "C7", "是关于宽恕"))
    seeds = extract_seeds(a, b, {"C7"}, CLUSTERS, TENSION_PAIRS)
    tension = [s for s in seeds if s.seed_type == "CREATIVE_TENSION"]
    assert len(tension) == 1
    assert tension[0].cluster == "C7"


def test_seeds_sorted_by_weight_desc():
    """多颗种子按 weight 降序。L3 簇 + tension 应排在前面。"""
    a = _persona(
        "A",
        Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "x"),
        Edge("BELIEVES", "野心会反噬人", 0.8, "C7", "y"),
        Edge("LIKES", "黑泽明", 0.95, "C7", "z"),
    )
    b = _persona(
        "B",
        Edge("FEELS_NOW", "留下还是离开", 0.85, "C1", "p"),
        Edge("BELIEVES", "乱是关于宽恕", 0.8, "C7", "q"),
        Edge("LIKES", "黑泽明", 0.9, "C7", "r"),
    )
    seeds = extract_seeds(a, b, {"C1", "C7"}, CLUSTERS, TENSION_PAIRS)
    weights = [s.weight for s in seeds]
    assert weights == sorted(weights, reverse=True)


def test_no_shared_cluster_no_seeds():
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "x"))
    b = _persona("B", Edge("LIKES", "黑泽明", 0.9, "C7", "y"))
    seeds = extract_seeds(a, b, set(), CLUSTERS, TENSION_PAIRS)
    assert seeds == []
