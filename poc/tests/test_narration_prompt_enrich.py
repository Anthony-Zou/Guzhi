"""Tests for build_narration_prompt 的 enrich 路径。

签名扩展为接收可选 supporting_edges。
- 不传 supporting_edges -> prompt 和原来完全一样 (向后兼容)
- 传 supporting_edges -> prompt 多一段【他们各自的其他心事】
- 不会篡改红线、不会重写 seed 主线
"""
from __future__ import annotations

from domain.models import Persona, Edge
from domain.narration_prompt import build_narration_prompt
from domain.seeds import StorySeed
from domain.supporting_edges import SupportingEdge


def _seed():
    return StorySeed(
        seed_type="RESONANCE", cluster="C1", weight=1.0,
        a_entity="回老家", b_entity="回老家",
        a_evidence="一直在想要不要回成都", b_evidence="也想过回",
    )


def _persona(pid="A", name="甲"):
    return Persona(
        id=pid, name=name, gender="female", archetype="测试",
        edges=(Edge(relation="SPEAKS_AS", entity="简短克制",
                    strength=0.8, cluster=None, evidence=""),),
    )


def _support(owner="A", entity="PPT 文化"):
    return SupportingEdge(
        owner=owner, relation="DISLIKES", entity=entity,
        strength=0.7, cluster="C1", evidence=f"我特别讨厌{entity}",
    )


class TestBackwardCompat:
    def test_no_supporting_edges_keeps_old_prompt(self):
        """不传 supporting_edges 时,prompt 和老 caller 看到的完全一样。"""
        p1 = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                    scene_seed=42)
        p2 = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                    scene_seed=42, supporting_edges=None)
        assert p1 == p2

    def test_empty_supporting_edges_keeps_old_prompt(self):
        """空列表也应等价于不传。"""
        p1 = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                    scene_seed=42)
        p2 = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                    scene_seed=42, supporting_edges=[])
        assert p1 == p2


class TestEnrichedPrompt:
    def test_supporting_edges_appear_in_prompt(self):
        edges = [_support("A", "PPT 文化"), _support("B", "团建")]
        p = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                   scene_seed=42, supporting_edges=edges)
        # 两条 entity 都应该被提到
        assert "PPT 文化" in p
        assert "团建" in p

    def test_supporting_section_labeled_by_owner(self):
        edges = [_support("A", "PPT 文化")]
        p = build_narration_prompt(_seed(), _persona("A", "甲"),
                                   _persona("B", "乙"),
                                   scene_seed=42, supporting_edges=edges)
        # owner=A 的边在 prompt 里应该挂到 a.name (甲) 下
        # 这里只断言两个出现得近 —— 不写死具体格式,留给实现选最自然的句式
        idx_name = p.find("甲")
        idx_entity = p.find("PPT 文化")
        assert idx_name != -1 and idx_entity != -1
        # entity 应该在 owner 名字之后 (语义上的"甲...PPT 文化")
        # 选个宽松约束:两者距离不超过 200 字
        assert abs(idx_entity - idx_name) < 200

    def test_supporting_edges_dont_change_red_lines(self):
        """红线段落必须仍然存在 —— enrich 不能稀释规则。"""
        edges = [_support("A", "X")]
        p = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                   scene_seed=42, supporting_edges=edges)
        # 红线第 2 条的关键词
        assert "不准泄露系统" in p
        # 红线第 4 条
        assert "不准编造" in p

    def test_supporting_edges_dont_replace_seed(self):
        """seed 的两句 evidence 仍然在,不被 supporting 覆盖。"""
        edges = [_support("A", "X")]
        p = build_narration_prompt(_seed(), _persona("A"), _persona("B", "乙"),
                                   scene_seed=42, supporting_edges=edges)
        assert "一直在想要不要回成都" in p   # a_evidence
        assert "也想过回" in p            # b_evidence
