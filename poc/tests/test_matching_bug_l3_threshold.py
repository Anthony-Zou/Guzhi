"""TDD — 回归测试：单个 L3 簇命中必须能稳定过门槛。

Bug 发现过程：30 人合成数据验证（修复 multicluster bug 后），
剩余 7 个 FN 全部是 shared={单个 L3 簇}，score 落在 0.083-0.100，
卡在 0.10 门槛附近 —— 一半过一半不过。

根因：单个 L3 簇命中的典型分数区间是 0.08-0.13
（feeling 权重 0.20 × 归一化值 ~0.4-0.5 × L3 加权 1.3）。
门槛 0.10 正好切在这个分布的中间。门槛 0.10 是当初拍脑袋定的。

生成器真值规则明确：共享 >=1 个 L3 簇即该匹配。
因此算法门槛必须让"单 L3 簇命中"稳定过线。

修复：含 L3 簇的门槛从 0.10 降到 0.07。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona, Cluster, ClusterLevel
from domain.matching import match

CLUSTERS = {
    "S1": Cluster("S1", "去留之惑", ClusterLevel.L3, "feeling_resonance"),
}


def _persona(pid, *edges):
    return Persona(id=pid, name=pid, edges=tuple(edges))


def test_weak_single_l3_cluster_still_matches():
    """即使双方 strength 都偏低（0.65），单个 L3 簇命中也该匹配。

    0.65*0.65=0.4225, /1.5=0.2817, *1.3=0.366, *0.20=0.0732
    必须 >= 门槛。
    """
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.65, "S1", "x"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.65, "S1", "y"))
    r = match(a, b, CLUSTERS, [], [])
    assert r.matched is True, (
        f"单个 L3 簇命中（哪怕弱）也该匹配，但 score={r.score} 没过门槛"
    )


def test_mid_strength_single_l3_matches():
    """中等 strength（0.75）的单 L3 簇命中，必须匹配。"""
    a = _persona("A", Edge("FEELS_NOW", "要不要回老家", 0.75, "S1", "x"))
    b = _persona("B", Edge("FEELS_NOW", "留下还是离开", 0.78, "S1", "y"))
    r = match(a, b, CLUSTERS, [], [])
    assert r.matched is True


def test_low_threshold_value():
    """显式锁定：低门槛（含 L3 或 >=2 簇的配对）应为 0.06。

    历史：原本叫 THRESHOLD_WITH_L3=0.07，只针对"含 L3"的配对。
    后来发现门槛该按"共享簇数量"分级（见 test_matching_bug_threshold_by_count），
    常量改名为 THRESHOLD_LOW，值下调到 0.06 以同时覆盖"单 L3 簇"和"两个 L1 簇"。
    """
    from domain.matching import THRESHOLD_LOW
    assert THRESHOLD_LOW == 0.06
