"""TDD — 回归测试：同一 signal 类别下多个簇命中，贡献应累加而非 max。

Bug 发现过程：30 人合成数据验证里，共享两个 L3 簇的人物
（如 SYN08-SYN25, shared={S1:L3, S2:L3}）反而算出极低分 0.094，
过不了门槛被漏掉（FN）。

根因：matching.py 用 `max(signals[sig], contribution)`，
两个 feeling_resonance 簇的贡献只取了大的，另一个被丢弃。

修复：同 signal 多簇命中时累加（带上限）。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona, Cluster, ClusterLevel
from domain.matching import match


# 两个 L3 簇，signal 都是 feeling_resonance —— 这是触发 bug 的关键配置
CLUSTERS = {
    "S1": Cluster("S1", "去留之惑", ClusterLevel.L3, "feeling_resonance"),
    "S2": Cluster("S2", "低谷停撑", ClusterLevel.L3, "feeling_resonance"),
}


def _persona(pid, *edges):
    return Persona(id=pid, name=pid, edges=tuple(edges))


def test_two_l3_clusters_should_score_higher_than_one():
    """共享两个 L3 簇，分数必须明显高于只共享一个。"""
    a_one = _persona("A1", Edge("FEELS_NOW", "要不要回老家", 0.9, "S1", "x"))
    b_one = _persona("B1", Edge("FEELS_NOW", "留下还是离开", 0.85, "S1", "y"))
    r_one = match(a_one, b_one, CLUSTERS, [], [])

    a_two = _persona(
        "A2",
        Edge("FEELS_NOW", "要不要回老家", 0.9, "S1", "x"),
        Edge("FEELS_NOW", "该不该停下来歇歇", 0.85, "S2", "z"),
    )
    b_two = _persona(
        "B2",
        Edge("FEELS_NOW", "留下还是离开", 0.85, "S1", "y"),
        Edge("FEELS_NOW", "是不是快撑不住了", 0.8, "S2", "w"),
    )
    r_two = match(a_two, b_two, CLUSTERS, [], [])

    # 核心断言：两个 L3 簇共鸣 > 一个 L3 簇共鸣
    assert r_two.score > r_one.score, (
        f"两个 L3 簇 ({r_two.score}) 居然不比一个 L3 簇 ({r_one.score}) 高"
    )
    # 两个深层共鸣点，必须能过门槛
    assert r_two.matched is True


def test_signal_capped_at_one():
    """累加后单类信号仍不能超过 1.0（防止分数失控）。"""
    # 构造很多个高强度 feeling_resonance 簇命中
    clusters = {
        f"S{i}": Cluster(f"S{i}", f"议题{i}", ClusterLevel.L3, "feeling_resonance")
        for i in range(1, 6)
    }
    a = _persona("A", *[
        Edge("FEELS_NOW", f"e{i}", 0.95, f"S{i}", "x") for i in range(1, 6)
    ])
    b = _persona("B", *[
        Edge("FEELS_NOW", f"f{i}", 0.95, f"S{i}", "y") for i in range(1, 6)
    ])
    r = match(a, b, clusters, [], [])
    # feeling_resonance 这一类信号的原始值不能超过 1.0
    assert r.signals["feeling_resonance"] <= 1.0
    # 总分也不能超过 1.0
    assert r.score <= 1.0
