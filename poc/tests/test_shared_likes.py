"""Tests for domain.shared_likes.compute_shared_likes。

从两个 Persona 找出"两人都 LIKES 同一 entity"的列表。

为什么这要写成纯函数:
- venue_prompt 需要它
- 但 venue prompt 不该自己扫 edges (那是低层细节)
- 把它单独抽出来,以后场地推荐之外的功能 (例如"匹配解释卡"也会用)
"""
from __future__ import annotations

from domain.models import Edge, Persona
from domain.shared_likes import compute_shared_likes


def _e(rel, entity, cluster="C7"):
    return Edge(relation=rel, entity=entity, strength=0.7,
                cluster=cluster, evidence="原话")


def _p(pid, edges):
    return Persona(id=pid, name=pid, gender="", archetype="", edges=tuple(edges))


class TestSharedLikes:
    def test_both_like_returns_entity(self):
        a = _p("A", [_e("LIKES", "日料")])
        b = _p("B", [_e("LIKES", "日料")])
        assert compute_shared_likes(a, b) == ["日料"]

    def test_one_likes_one_dislikes_returns_empty(self):
        """LIKES vs DISLIKES 不算共同偏好。"""
        a = _p("A", [_e("LIKES", "团建")])
        b = _p("B", [_e("DISLIKES", "团建")])
        assert compute_shared_likes(a, b) == []

    def test_returns_only_intersection(self):
        a = _p("A", [_e("LIKES", "日料"), _e("LIKES", "巴赫")])
        b = _p("B", [_e("LIKES", "日料"), _e("LIKES", "村上春树")])
        assert compute_shared_likes(a, b) == ["日料"]

    def test_deterministic_order(self):
        """同输入,任何调用顺序,输出 list 顺序一致 (字典序)。"""
        a = _p("A", [_e("LIKES", "B 项"), _e("LIKES", "A 项")])
        b = _p("B", [_e("LIKES", "A 项"), _e("LIKES", "B 项")])
        out = compute_shared_likes(a, b)
        assert out == sorted(out)

    def test_empty_personas(self):
        a = _p("A", [])
        b = _p("B", [])
        assert compute_shared_likes(a, b) == []

    def test_non_likes_relations_ignored(self):
        """FEELS_NOW / BELIEVES / EXPERIENCED 不算"共同偏好" —— 那些进 narrate,
        不该误进场地推荐 prompt。"""
        a = _p("A", [_e("FEELS_NOW", "想躺平")])
        b = _p("B", [_e("FEELS_NOW", "想躺平")])
        assert compute_shared_likes(a, b) == []
