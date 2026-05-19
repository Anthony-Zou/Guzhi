"""Tests for app.feeding_service.FeedingService。

行为契约:
  feed(persona_id, text) ->
    1. extract(text, call_point=DAILY_FEED_EXTRACT) -> 一组新 edges
    2. 合到已有 Persona (用 merge_edges)
    3. upsert 回 repo
    4. 算 Acknowledgement 并返回

不主动陪聊 —— ack 信息靠 to_message() 渲染,FeedingService 自己不生成对话。
"""
from __future__ import annotations

import os
import sys
from dataclasses import replace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from adapters.in_memory_repository import InMemoryPersonaRepository
from adapters.stub_extractor import StubKnowledgeExtractor
from app.feeding_service import FeedingService
from domain.acknowledgement import Acknowledgement
from domain.models import Cluster, ClusterLevel, Edge, Persona
from ports.knowledge_extractor import KnowledgeExtractor


def _clusters() -> dict[str, Cluster]:
    return {
        "C1": Cluster(id="C1", name="去留之惑", level=ClusterLevel.L3, signal="S_DRIFT"),
        "C2": Cluster(id="C2", name="反效率主义", level=ClusterLevel.L2, signal="S_VALUE"),
        "C7": Cluster(id="C7", name="电影品味", level=ClusterLevel.L1, signal="S_TASTE"),
    }


def _make_repo(personas: list[Persona] | None = None) -> InMemoryPersonaRepository:
    return InMemoryPersonaRepository(
        personas=personas or [],
        clusters=_clusters(),
        tension_pairs=[],
        style_complement_pairs=[],
    )


def _base_persona(pid: str = "U1", edges: tuple[Edge, ...] = ()) -> Persona:
    return Persona(id=pid, name="测试者", gender="", archetype="", edges=edges)


class _FakeExtractor(KnowledgeExtractor):
    """可注入的 fake:返回事先指定的 edges。"""
    def __init__(self, edges: list[Edge]) -> None:
        self._edges = edges
        self.last_call_point: str | None = "NOT_CALLED"
        self.last_text: str | None = None

    def extract(self, text, persona_id, name, gender="", call_point=None):
        self.last_text = text
        self.last_call_point = call_point
        return Persona(
            id=persona_id, name=name, gender=gender,
            archetype="", edges=tuple(self._edges),
        )


class TestFeedHappyPath:
    def test_extracts_with_daily_feed_call_point(self):
        """投喂走 DAILY_FEED_EXTRACT,提示 RoutedExtractor 路由到 Haiku。"""
        from domain.routing import CallPoint
        repo = _make_repo([_base_persona()])
        extractor = _FakeExtractor([])
        svc = FeedingService(repo=repo, extractor=extractor)

        svc.feed("U1", "听了一首歌")

        assert extractor.last_call_point == CallPoint.DAILY_FEED_EXTRACT

    def test_merges_new_edges_into_existing(self):
        """投喂后,repo 里的 persona edges 应该是 merge 后的结果。"""
        old = Edge(relation="LIKES", entity="山", strength=0.6,
                   cluster="C7", evidence="原本")
        repo = _make_repo([_base_persona(edges=(old,))])
        new_edge = Edge(relation="LIKES", entity="海", strength=0.5,
                        cluster="C7", evidence="新加")
        extractor = _FakeExtractor([new_edge])
        svc = FeedingService(repo=repo, extractor=extractor)

        svc.feed("U1", "今天去了海边")

        p = repo.get("U1")
        entities = {e.entity for e in p.edges}
        assert entities == {"山", "海"}

    def test_returns_acknowledgement_with_touched_clusters(self):
        repo = _make_repo([_base_persona()])
        extractor = _FakeExtractor([
            Edge(relation="FEELS_NOW", entity="想躺平", strength=0.8,
                 cluster="C1", evidence="想躺平"),
            Edge(relation="DISLIKES", entity="PPT 文化", strength=0.7,
                 cluster="C2", evidence="讨厌"),
        ])
        svc = FeedingService(repo=repo, extractor=extractor)

        ack = svc.feed("U1", "想躺平 + 讨厌 PPT 文化")

        assert isinstance(ack, Acknowledgement)
        assert ack.new_edge_count == 2
        cluster_ids = {cid for cid, _ in ack.touched_clusters}
        assert cluster_ids == {"C1", "C2"}

    def test_noise_edges_recorded_in_ack(self):
        """抽出 cluster=None 的边时,had_noise = True。"""
        repo = _make_repo([_base_persona()])
        extractor = _FakeExtractor([
            Edge(relation="LIKES", entity="某个未归簇的东西",
                 strength=0.5, cluster=None, evidence="某句话"),
        ])
        svc = FeedingService(repo=repo, extractor=extractor)

        ack = svc.feed("U1", "blah")

        assert ack.had_noise is True


class TestEdgeCases:
    def test_unknown_persona_raises(self):
        repo = _make_repo([])
        extractor = _FakeExtractor([])
        svc = FeedingService(repo=repo, extractor=extractor)
        with pytest.raises(KeyError):
            svc.feed("does-not-exist", "text")

    def test_empty_extract_returns_zero_count_ack(self):
        """LLM 没抽出任何边时,返回 new_edge_count=0 的诚实 ack。"""
        repo = _make_repo([_base_persona()])
        extractor = _FakeExtractor([])
        svc = FeedingService(repo=repo, extractor=extractor)
        ack = svc.feed("U1", "无意义文本")
        assert ack.new_edge_count == 0
        assert "没" in ack.to_message() or "无" in ack.to_message()

    def test_duplicate_edge_does_not_inflate_count(self):
        """重复边 (max strength 合并) 不算"新边"。"""
        old = Edge(relation="LIKES", entity="山", strength=0.5,
                   cluster="C7", evidence="原本")
        repo = _make_repo([_base_persona(edges=(old,))])
        # 抽出同样的边但 strength 更高
        extractor = _FakeExtractor([
            Edge(relation="LIKES", entity="山", strength=0.9,
                 cluster="C7", evidence="原本更长一些"),
        ])
        svc = FeedingService(repo=repo, extractor=extractor)
        ack = svc.feed("U1", "...")
        assert ack.new_edge_count == 0   # 没增加新边
        # 但已有边的 strength 应当被 boost 了
        p = repo.get("U1")
        e = next(e for e in p.edges if e.entity == "山")
        assert e.strength == 0.9


class TestRepoMustSupportUpsert:
    def test_readonly_repo_raises_helpful_error(self):
        """如果 repo 没 add 方法,FeedingService 应该报清楚的错。"""
        class _ReadOnly:
            def get(self, pid):
                return _base_persona()
            def clusters(self):
                return _clusters()
            def all_personas(self):
                return []
            def tension_pairs(self):
                return []
            def style_complement_pairs(self):
                return []
        # 没有 add() 方法的 repo
        svc = FeedingService(repo=_ReadOnly(), extractor=_FakeExtractor([]))  # type: ignore[arg-type]
        with pytest.raises(RuntimeError, match="add"):
            svc.feed("U1", "text")
