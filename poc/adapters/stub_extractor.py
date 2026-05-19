"""adapter — StubKnowledgeExtractor。

实现 KnowledgeExtractor 端口，但不真调 AI。靠"关键词子串匹配"抽边：
文本里出现了 TraitLibrary 里某个 entity 的字样，就抽出对应的边。

它的局限很明显（只能抽预设关键词、不懂同义改写、不懂语气强度），
正好凸显了"为什么需要真 LLM"。POC 阶段用它验证链路接通：
文本 -> Persona -> 匹配 -> 推演 这条路能跑通。

复用 synthetic.generator.TraitLibrary —— 那里已经有 entity->簇->relation 的映射。
"""
from __future__ import annotations

from domain.models import Edge, Persona
from ports.knowledge_extractor import KnowledgeExtractor
from synthetic.generator import TraitLibrary


class StubKnowledgeExtractor(KnowledgeExtractor):
    def __init__(self, library: TraitLibrary | None = None) -> None:
        self._lib = library or TraitLibrary.default()
        # 预建一张 (entity -> (cluster_id, relation)) 的查找表
        self._entity_index: dict[str, tuple[str, str]] = {}
        for cid, entities in self._lib.cluster_entities.items():
            relation = self._lib.cluster_relation[cid]
            for ent in entities:
                self._entity_index[ent] = (cid, relation)

    def extract(self, text: str, persona_id: str,
                name: str, gender: str = "",
                call_point: str | None = None) -> Persona:
        del call_point  # stub 不路由
        edges: list[Edge] = []
        # 关键词子串匹配：文本里出现 entity 字样就抽出对应的边
        # 按 entity 名排序，保证确定性
        for ent in sorted(self._entity_index):
            if ent in text:
                cid, relation = self._entity_index[ent]
                edges.append(Edge(
                    relation=relation,
                    entity=ent,
                    strength=0.75,  # stub 用固定强度 —— 它不懂语气
                    cluster=cid,
                    evidence=f"（stub 抽取）文本中出现「{ent}」",
                ))
        return Persona(id=persona_id, name=name,
                       edges=tuple(edges), gender=gender, archetype="")
