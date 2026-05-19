"""TDD — 回归测试：门槛逻辑应按"共享簇数量"分级，不只按"有无 L3"。

Bug 发现过程：扩充 entity 库（60 -> 120 个）后，30 人合成数据集
暴露两个系统性问题：
  - FN（漏配）：共享两个 L1 簇的人，真值表说该匹配（生成器规则：
    共享 >=2 个簇就该匹配），但算法用 0.15 默认门槛，两个 L1 簇
    典型分数 0.10-0.15，卡在门槛下面。
  - FP（误配）：只共享单个 L2 簇的人，真值表说不该匹配（单簇不够），
    但分数能到 0.15-0.16，擦过门槛。

根因：门槛只按 has_L3 分两档。但生成器真值规则的本质是"共享簇的
数量"——共享 >=1 个 L3 簇，或 >=2 个任意簇，就该匹配。

修复：门槛逻辑跟生成器规则对齐：
  - 含 L3 簇，或 共享 >=2 个簇 -> 低门槛 THRESHOLD_LOW
  - 只有单个非 L3 簇        -> 高门槛 THRESHOLD_HIGH
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona, Cluster, ClusterLevel
from domain.matching import match


def _persona(pid, *edges):
    return Persona(id=pid, name=pid, edges=tuple(edges))


# ---- 两个 L1 簇 ----
TWO_L1 = {
    "L1a": Cluster("L1a", "文艺片", ClusterLevel.L1, "shared_passion"),
    "L1b": Cluster("L1b", "古典乐", ClusterLevel.L1, "shared_passion"),
}


def test_two_l1_clusters_should_match():
    """共享两个 L1 簇 -> 该匹配（对齐生成器规则：>=2 个簇就该匹配）。

    哪怕 strength 偏低、分数只有 0.10-0.13，也必须匹配。
    """
    a = _persona(
        "A",
        Edge("LIKES", "侯孝贤", 0.7, "L1a", "x"),
        Edge("LIKES", "巴赫", 0.7, "L1b", "y"),
    )
    b = _persona(
        "B",
        Edge("LIKES", "杨德昌", 0.7, "L1a", "p"),
        Edge("LIKES", "肖邦", 0.7, "L1b", "q"),
    )
    r = match(a, b, TWO_L1, [], [])
    assert r.matched is True, (
        f"共享两个 L1 簇该匹配，但 score={r.score} 没过门槛"
    )


# ---- 单个 L2 簇 ----
ONE_L2 = {
    "L2x": Cluster("L2x", "形式之美", ClusterLevel.L2, "belief_alignment"),
}


def test_single_l2_cluster_should_not_match():
    """只共享单个 L2 簇 -> 不该匹配（生成器规则：单簇不够）。

    哪怕 strength 很高、分数到 0.15-0.16，也必须判不匹配。
    """
    a = _persona("A", Edge("BELIEVES", "克制的设计最美", 0.95, "L2x", "x"))
    b = _persona("B", Edge("BELIEVES", "少即是多", 0.95, "L2x", "y"))
    r = match(a, b, ONE_L2, [], [])
    assert r.matched is False, (
        f"单个 L2 簇不该匹配，但 score={r.score} 过了门槛"
    )


def test_single_l3_cluster_still_matches():
    """回归保护：单个 L3 簇仍然该匹配（之前修过的 bug 不能退化）。"""
    one_l3 = {
        "L3x": Cluster("L3x", "去留之惑", ClusterLevel.L3, "feeling_resonance"),
    }
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.7, "L3x", "x"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.7, "L3x", "y"))
    r = match(a, b, one_l3, [], [])
    assert r.matched is True


def test_two_l2_clusters_should_match():
    """共享两个 L2 簇 -> 该匹配（>=2 个簇）。"""
    two_l2 = {
        "L2a": Cluster("L2a", "反效率", ClusterLevel.L2, "belief_alignment"),
        "L2b": Cluster("L2b", "独立自主", ClusterLevel.L2, "belief_alignment"),
    }
    a = _persona(
        "A",
        Edge("BELIEVES", "慢下来不是错", 0.75, "L2a", "x"),
        Edge("BELIEVES", "不依附任何机构", 0.75, "L2b", "y"),
    )
    b = _persona(
        "B",
        Edge("BELIEVES", "效率不是最高价值", 0.75, "L2a", "p"),
        Edge("BELIEVES", "自己定义成功", 0.75, "L2b", "q"),
    )
    r = match(a, b, two_l2, [], [])
    assert r.matched is True
