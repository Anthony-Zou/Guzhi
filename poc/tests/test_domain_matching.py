"""TDD — domain 层匹配引擎测试。

这是整个 POC 的核心。手算验证过的结果在这里被固化成自动化测试。
匹配引擎是纯函数：输入两个 Persona + 簇定义，输出 MatchResult。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona, Cluster, ClusterLevel
from domain.matching import match, MatchResult


# ---- 测试用簇定义（取设计文档 v0.2 的子集）----
CLUSTERS = {
    "C1": Cluster("C1", "去留之惑", ClusterLevel.L3, "feeling_resonance"),
    "C2": Cluster("C2", "反效率主义", ClusterLevel.L2, "belief_alignment"),
    "C3": Cluster("C3", "反正能量表演", ClusterLevel.L1, "shared_aversion"),
    "C7": Cluster("C7", "电影品味", ClusterLevel.L1, "shared_passion"),
    "C8": Cluster("C8", "行动派反内耗", ClusterLevel.L1, "shared_passion"),
}
TENSION_PAIRS = [("C7", "野心会反噬人", "乱是关于宽恕")]
STYLE_COMPLEMENT = [("锐利批判", "温柔细腻")]


def _persona(pid, *edges):
    return Persona(id=pid, name=pid, edges=tuple(edges))


# ============================================================
# 闸门测试
# ============================================================

def test_zero_shared_cluster_means_no_match():
    """零共簇闸：两人没有任何共享语义簇 -> 无匹配。这是排除 P7 的机制。"""
    a = _persona("A", Edge("LIKES", "黑泽明", 0.95, "C7", "x"))
    b = _persona("B", Edge("LIKES", "运动", 0.9, "C8", "y"))
    r = match(a, b, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert r.matched is False
    assert r.reason == "zero_shared_cluster"


def test_single_L1_cluster_only_means_no_match():
    """L1 单簇闸：只共享一个 L1 偏好簇 -> 不够，无匹配。"""
    a = _persona("A", Edge("DISLIKES", "积极心理学话术", 0.9, "C3", "x"))
    b = _persona("B", Edge("DISLIKES", "过度热情的客套", 0.85, "C3", "y"))
    r = match(a, b, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert r.matched is False
    assert r.reason == "single_L1_cluster"


def test_L3_single_cluster_can_match_with_low_threshold():
    """含 L3 簇的配对：门槛 0.10，单 L3 簇即可成立。"""
    # 两人只共享 C1（L3 去留之惑），别无其他
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "x"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.85, "C1", "y"))
    r = match(a, b, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert r.matched is True
    # feeling: 0.9*0.85=0.765, /1.5=0.51, *1.3(L3)=0.663, *0.20(权重)=0.1326
    assert 0.12 < r.score < 0.14


# ============================================================
# 手算结果固化（来自设计文档第三轮 v0.3 算法）
# ============================================================

def test_p1_p2_full_match_score():
    """P1 林知 ╳ P2 周临 —— 设计文档手算 = 0.417。
    共簇 C7(L1,对立->tension), C1(L3), C2(L2)。
    """
    p1 = _persona(
        "P1",
        Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "x"),
        Edge("LIKES", "黑泽明", 0.95, "C7", "y"),
        Edge("BELIEVES", "野心会反噬人", 0.8, "C7", "z"),
        Edge("BELIEVES", "慢下来不是错", 0.8, "C2", "w"),
        Edge("DISLIKES", "加班崇拜", 0.85, "C2", "v"),
    )
    p2 = _persona(
        "P2",
        Edge("FEELS_NOW", "五年前的我会怎么看现在的我", 0.75, "C1", "x"),
        Edge("LIKES", "黑泽明", 0.9, "C7", "y"),
        Edge("BELIEVES", "乱是关于宽恕", 0.8, "C7", "z"),
        Edge("BELIEVES", "人不需要一直证明自己", 0.85, "C2", "w"),
    )
    r = match(p1, p2, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert r.matched is True
    # 手算 0.417，允许 ±0.03 容差（手算有舍入）
    assert 0.39 < r.score < 0.45
    # creative_tension 必须命中（C7 簇内对立）
    assert r.signals["creative_tension"] == 1.0


def test_p7_matches_nobody():
    """P7 唐越和谁都不该匹配——它跟所有人零共簇。"""
    p7 = _persona(
        "P7",
        Edge("LIKES", "运动", 0.9, "C8", "x"),
        Edge("DISLIKES", "内耗", 0.85, "C8", "y"),
        Edge("BELIEVES", "状态是可以选择的", 0.85, "C8", "z"),
    )
    # 跟一个典型的"深沉型"人物
    other = _persona(
        "X",
        Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "a"),
        Edge("BELIEVES", "慢下来不是错", 0.8, "C2", "b"),
    )
    r = match(p7, other, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert r.matched is False


def test_match_is_symmetric():
    """match(A,B) 和 match(B,A) 分数应该相同。"""
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "x"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.85, "C1", "y"))
    r1 = match(a, b, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    r2 = match(b, a, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert abs(r1.score - r2.score) < 1e-9


def test_match_result_carries_explanation():
    """MatchResult 必须能解释分数怎么来的——可解释性是 KG-First 的卖点。"""
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.9, "C1", "x"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.85, "C1", "y"))
    r = match(a, b, CLUSTERS, TENSION_PAIRS, STYLE_COMPLEMENT)
    assert "feeling_resonance" in r.signals
    assert "C1" in r.shared_clusters
