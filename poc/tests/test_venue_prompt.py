"""Tests for domain.venue_prompt.build_venue_prompt。

输入:两个人 + 双方共享的 LIKES 边 (来自 KG 共簇)
输出:给 LLM 的 prompt,要求生成一段场地推荐文本

关键约束:
- 只能基于两人都 LIKES 的具体偏好生成推荐
- 不准编造具体商家 (我们不接 O2O,所以不该让 LLM 装作有数据)
- 输出短文本 (~2-3 句),不要列表,不要旅游攻略
- 不准像 dating app 那样推"约会胜地" —— 故知的语气是克制的
"""
from __future__ import annotations

from domain.models import Edge, Persona
from domain.venue_prompt import build_venue_prompt


def _p(pid="A", name="甲", likes=None):
    edges = tuple(
        Edge(relation="LIKES", entity=ent, strength=0.8,
             cluster="C7", evidence=f"原话:喜欢{ent}")
        for ent in (likes or [])
    )
    return Persona(id=pid, name=name, gender="", archetype="", edges=edges)


class TestStructure:
    def test_contains_both_names(self):
        a = _p("A", "林知", likes=["独立书店"])
        b = _p("B", "周临", likes=["独立书店"])
        shared = ["独立书店"]
        prompt = build_venue_prompt(a, b, shared_likes=shared)
        assert "林知" in prompt
        assert "周临" in prompt

    def test_lists_shared_likes(self):
        a = _p("A", "林知", likes=["日料", "独立书店"])
        b = _p("B", "周临", likes=["日料", "独立书店"])
        prompt = build_venue_prompt(a, b, shared_likes=["日料", "独立书店"])
        assert "日料" in prompt
        assert "独立书店" in prompt

    def test_red_lines_present(self):
        """这个 prompt 也有它自己的红线 (不准编商家、不要旅游攻略口吻)。"""
        a = _p("A", "林知", likes=["日料"])
        b = _p("B", "周临", likes=["日料"])
        prompt = build_venue_prompt(a, b, shared_likes=["日料"])
        # 关键红线
        assert "不准编造" in prompt or "不要编" in prompt
        assert "不要旅游" in prompt or "不是攻略" in prompt or "克制" in prompt

    def test_short_output_directive(self):
        """要求短文本 —— prompt 里得告诉 LLM。"""
        a = _p("A", "林知", likes=["日料"])
        b = _p("B", "周临", likes=["日料"])
        prompt = build_venue_prompt(a, b, shared_likes=["日料"])
        # 应当有"两三句"或"短"或类似限制
        assert "句" in prompt or "短" in prompt


class TestEmptySharedLikes:
    def test_empty_shared_likes_still_buildable(self):
        """没共同 LIKES 时 prompt 仍应可构建,只是 LLM 该给出"暂无明显共同偏好"
        类似的兜底语。 prompt 自己不该 crash。"""
        a = _p("A", "甲", likes=[])
        b = _p("B", "乙", likes=[])
        prompt = build_venue_prompt(a, b, shared_likes=[])
        assert "甲" in prompt
        assert "乙" in prompt
