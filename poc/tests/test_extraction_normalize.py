"""TDD — 抽取结果归一化测试（domain 层纯函数）。

LLM 抽出来的 raw 边是不可信的：可能 strength 越界、可能引用不存在的簇、
可能 entity 是同义改写。normalize_edges 把 raw 边洗成可用的 Edge。

这是 domain 层纯函数：归一化规则是领域知识，不碰 IO。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge
from domain.extraction_normalize import normalize_edges, NormalizeContext


# 一个最小的归一化上下文：合法簇 + entity->簇 映射 + 别名表
CTX = NormalizeContext(
    valid_clusters={"S1", "S2", "S5"},
    entity_to_cluster={
        "要不要回老家": ("S1", "FEELS_NOW"),
        "留下还是离开": ("S1", "FEELS_NOW"),
        "该不该停下来歇歇": ("S2", "FEELS_NOW"),
        "人不该被KPI量化": ("S5", "BELIEVES"),
    },
    entity_aliases={
        "想回老家": "要不要回老家",      # 同义改写 -> 规范名
        "要不要回家乡": "要不要回老家",
    },
)


def _raw(relation, entity, strength, cluster):
    """模拟 LLM 返回的一条 raw 边（dict 形式）。"""
    return {"relation": relation, "entity": entity,
            "strength": strength, "cluster": cluster,
            "evidence": f"原话：{entity}"}


def test_valid_edge_passes_through():
    """一条干净的边，原样通过（变成 Edge 对象）。"""
    raw = [_raw("FEELS_NOW", "要不要回老家", 0.8, "S1")]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 1
    assert isinstance(edges[0], Edge)
    assert edges[0].entity == "要不要回老家"
    assert edges[0].cluster == "S1"


def test_strength_out_of_range_is_clamped():
    """strength 越界 -> clamp 到 [0,1]，不丢弃。"""
    raw = [
        _raw("FEELS_NOW", "要不要回老家", 1.8, "S1"),
        _raw("FEELS_NOW", "留下还是离开", -0.3, "S1"),
    ]
    edges = normalize_edges(raw, CTX)
    strengths = sorted(e.strength for e in edges)
    assert strengths == [0.0, 1.0]


def test_unknown_cluster_downgraded_to_noise():
    """LLM 引用了不存在的簇（幻觉编了个簇 id）-> 降级成噪音边，不污染 KG。

    设计选择：不丢弃整条边。entity 信息本身可能是真的，只是 LLM 把它
    硬塞进了一个不存在的簇。降级成噪音边（cluster=None）—— 它进不了
    匹配（匹配只看簇），但信息保留下来。
    这和 test_unknown_entity_kept_as_noise_edge 是同一条原则。
    """
    raw = [
        _raw("FEELS_NOW", "要不要回老家", 0.8, "S1"),
        _raw("FEELS_NOW", "瞎编的", 0.8, "S99"),  # S99 不存在
    ]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 2
    by_entity = {e.entity: e for e in edges}
    # 已知 entity 正常进簇
    assert by_entity["要不要回老家"].cluster == "S1"
    # 未知 entity + 非法簇 -> 降级为噪音边
    assert by_entity["瞎编的"].cluster is None


def test_entity_alias_is_resolved():
    """LLM 用了同义改写 -> 归一到规范 entity 名 + 对应的簇。"""
    raw = [_raw("FEELS_NOW", "想回老家", 0.8, "S1")]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 1
    assert edges[0].entity == "要不要回老家"   # 别名被解析成规范名


def test_cluster_corrected_from_entity_index():
    """LLM 把 entity 归错了簇 -> 用 entity_to_cluster 表纠正。"""
    # "人不该被KPI量化" 真实属于 S5，但 LLM 说成 S1
    raw = [_raw("FEELS_NOW", "人不该被KPI量化", 0.8, "S1")]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 1
    assert edges[0].cluster == "S5"            # 纠正成 S5
    assert edges[0].relation == "BELIEVES"     # relation 也按表纠正


def test_unknown_entity_kept_as_noise_edge():
    """LLM 抽出一个不在库里的 entity -> 保留为噪音边（cluster=None），不丢弃。

    理由：未知 entity 可能是真实的、只是库没收录。当噪音边留着，
    不进匹配，但保留信息。
    """
    raw = [_raw("LIKES", "组装机械键盘", 0.7, None)]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 1
    assert edges[0].cluster is None
    assert edges[0].entity == "组装机械键盘"


def test_duplicate_entities_deduplicated():
    """同一 entity 抽了两次 -> 去重，保留 strength 较高的。"""
    raw = [
        _raw("FEELS_NOW", "要不要回老家", 0.6, "S1"),
        _raw("FEELS_NOW", "要不要回老家", 0.9, "S1"),
    ]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 1
    assert edges[0].strength == 0.9


def test_malformed_raw_edge_is_skipped():
    """raw 边缺字段 -> 跳过，不崩。"""
    raw = [
        {"relation": "FEELS_NOW"},  # 缺 entity
        _raw("FEELS_NOW", "要不要回老家", 0.8, "S1"),
    ]
    edges = normalize_edges(raw, CTX)
    assert len(edges) == 1
    assert edges[0].entity == "要不要回老家"
