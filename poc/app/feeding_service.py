"""app 层 —— FeedingService。

弱养成的入口:
  user.feed(text) -> extract(call_point=DAILY_FEED_EXTRACT) -> merge_edges
  -> upsert persona -> 返回 Acknowledgement

故知的产品决定:
- agent 不主动陪聊 —— 投喂后只回一句"记下了 · ..."
- 这条规则在 Acknowledgement.to_message() 里执行 (域层)
- FeedingService 只负责编排,不写对话

依赖端口:
- PersonaRepository (读 + 写,需 add 方法)
- KnowledgeExtractor (注入 RoutedExtractor 则会路由到 Haiku)
"""
from __future__ import annotations

from dataclasses import replace

from domain.acknowledgement import Acknowledgement
from domain.merge_edges import merge_edges
from domain.models import Edge, Persona
from domain.routing import CallPoint
from ports.knowledge_extractor import KnowledgeExtractor
from ports.persona_repository import PersonaRepository


class FeedingService:
    def __init__(self, repo: PersonaRepository,
                 extractor: KnowledgeExtractor) -> None:
        self._repo = repo
        self._extractor = extractor

    def feed(self, persona_id: str, text: str) -> Acknowledgement:
        """投喂入口。"""
        # repo 必须支持写。读时拿到的可能是不可变 Persona,merge 后要 add 回去。
        add = getattr(self._repo, "add", None)
        if add is None:
            raise RuntimeError(
                "FeedingService 需要一个支持写的 repo (要有 add 方法)。"
                "InMemoryPersonaRepository 满足要求;只读的 JsonPersonaRepository 不行。"
            )

        # 1) 取现有 persona —— 找不到 -> KeyError 自然往上抛
        existing = self._repo.get(persona_id)

        # 2) 抽 (走 DAILY_FEED_EXTRACT,RoutedExtractor 会路由到 Haiku)
        extracted = self._extractor.extract(
            text,
            persona_id=existing.id,
            name=existing.name,
            gender=existing.gender,
            call_point=CallPoint.DAILY_FEED_EXTRACT,
        )

        # 3) 合并
        merged_edges = merge_edges(
            existing=existing.edges,
            new=extracted.edges,
        )

        # 4) upsert
        updated = replace(existing, edges=merged_edges)
        add(updated)

        # 5) 算 ack:数"真的新增了多少条 (max-merge 不算新)"
        ack = self._make_ack(
            existing_edges=existing.edges,
            extracted_edges=tuple(extracted.edges),
        )
        return ack

    def _make_ack(self, *, existing_edges: tuple[Edge, ...],
                  extracted_edges: tuple[Edge, ...]) -> Acknowledgement:
        existing_keys = {(e.relation, e.entity) for e in existing_edges}
        truly_new = [
            e for e in extracted_edges
            if (e.relation, e.entity) not in existing_keys
        ]

        # 触发了哪些簇 (用 catalog 查 name);按 cid 字典序;去重
        clusters_catalog = self._repo.clusters()
        touched_set: set[tuple[str, str]] = set()
        had_noise = False
        for e in extracted_edges:
            if e.cluster is None:
                had_noise = True
                continue
            if e.cluster in clusters_catalog:
                touched_set.add((e.cluster, clusters_catalog[e.cluster].name))

        touched = tuple(sorted(touched_set, key=lambda t: t[0]))

        return Acknowledgement(
            new_edge_count=len(truly_new),
            touched_clusters=touched,
            had_noise=had_noise,
        )
