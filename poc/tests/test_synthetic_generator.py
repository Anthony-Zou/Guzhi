"""TDD — 合成数据生成器测试。

生成器从特质库组合出人物。真值表是生成规则的机械产物，不是主观判断。

防作弊核心：生成器判定"该不该匹配"用的是简单集合计数规则，
匹配算法用的是带 strength/normalize/深度加权的打分。两者逻辑不同，
若结果高度一致，才说明算法的复杂打分确实在做正确的事。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Persona, ClusterLevel
from synthetic.generator import (
    TraitLibrary, PersonaGenerator, ground_truth_for,
)


def _library():
    return TraitLibrary.default()


def test_library_has_clusters_at_three_levels():
    lib = _library()
    levels = {c.level for c in lib.clusters.values()}
    assert ClusterLevel.L1 in levels
    assert ClusterLevel.L2 in levels
    assert ClusterLevel.L3 in levels


def test_library_each_cluster_has_multiple_entities():
    """每个簇至少 3 个不同 entity，这样不同人能共享簇但 entity 不同。"""
    lib = _library()
    for cid, entities in lib.cluster_entities.items():
        assert len(entities) >= 3, f"{cid} 的 entity 太少"


def test_generator_is_deterministic_with_seed():
    """同一 seed 必须生成同样的人物——可复现是验证的前提。"""
    g1 = PersonaGenerator(_library(), seed=42)
    g2 = PersonaGenerator(_library(), seed=42)
    p1 = g1.generate(count=10)
    p2 = g2.generate(count=10)
    assert [p.id for p in p1] == [p.id for p in p2]
    assert [tuple(e.entity for e in p.edges) for p in p1] == \
           [tuple(e.entity for e in p.edges) for p in p2]


def test_generates_requested_count():
    g = PersonaGenerator(_library(), seed=1)
    personas = g.generate(count=30)
    assert len(personas) == 30
    ids = {p.id for p in personas}
    assert len(ids) == 30  # id 不重复


def test_each_persona_has_clustered_and_noise_edges():
    """每个人物既有归簇的边，也有噪音边（不属任何簇）。"""
    g = PersonaGenerator(_library(), seed=1)
    personas = g.generate(count=30)
    for p in personas:
        clustered = [e for e in p.edges if e.cluster is not None]
        noise = [e for e in p.edges if e.cluster is None]
        assert len(clustered) >= 2, f"{p.id} 归簇边太少"
        assert len(noise) >= 1, f"{p.id} 没有噪音边"


def test_ground_truth_is_mechanical():
    """真值表是机械规则的产物：共享 >=1 个 L3 簇，或 >=2 个任意簇 -> 该匹配。

    这个规则独立于匹配算法。它是'设计意图'。
    """
    g = PersonaGenerator(_library(), seed=1)
    personas = g.generate(count=30)
    lib = _library()
    truth = ground_truth_for(personas, lib)

    # truth 的结构：{pid: set(应该匹配的 pid)}
    assert isinstance(truth, dict)
    # 对称性：a 在 b 的真值里 <=> b 在 a 的真值里
    for pid, partners in truth.items():
        for partner in partners:
            assert pid in truth[partner], f"真值表不对称: {pid}-{partner}"


def test_ground_truth_rule_l3_single():
    """验证规则：只共享一个 L3 簇也算该匹配。"""
    from synthetic.generator import _should_match
    lib = _library()
    # 构造两个只共享一个 L3 簇的人
    l3_cluster = next(c.id for c in lib.clusters.values()
                      if c.level == ClusterLevel.L3)
    a_clusters = {l3_cluster}
    b_clusters = {l3_cluster}
    assert _should_match(a_clusters, b_clusters, lib) is True


def test_ground_truth_rule_single_l1_not_enough():
    """验证规则：只共享一个 L1 簇不算该匹配。"""
    from synthetic.generator import _should_match
    lib = _library()
    l1_cluster = next(c.id for c in lib.clusters.values()
                      if c.level == ClusterLevel.L1)
    assert _should_match({l1_cluster}, {l1_cluster}, lib) is False


def test_ground_truth_rule_two_clusters_enough():
    """验证规则：共享 2 个簇（哪怕都是 L1）算该匹配。"""
    from synthetic.generator import _should_match
    lib = _library()
    l1s = [c.id for c in lib.clusters.values()
           if c.level == ClusterLevel.L1]
    assert len(l1s) >= 2
    shared = {l1s[0], l1s[1]}
    assert _should_match(shared, shared, lib) is True
