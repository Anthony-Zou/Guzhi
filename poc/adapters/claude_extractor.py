"""adapter — ClaudeKnowledgeExtractor。

实现 KnowledgeExtractor 端口。组合四样东西：
  - build_extraction_prompt   构建 prompt（领域逻辑）
  - LLMClient                 真正调 LLM（注入）
  - JSON 解析                 容错地从 LLM 输出里抠出 JSON
  - normalize_edges           洗成可信的 Edge（领域逻辑）

adapter 的本分：把领域逻辑和 IO 接起来，自己不碰 prompt 设计、
不碰归一化规则、不碰 anthropic SDK。

从 TraitLibrary 派生出 prompt 需要的 cluster_guide 和归一化需要的
NormalizeContext —— 这样 extractor 知道"有哪些簇、entity 该归哪"。
"""
from __future__ import annotations

import json

from domain.models import Persona
from domain.extraction_prompt import build_extraction_prompt, ClusterGuide
from domain.extraction_normalize import normalize_edges, NormalizeContext
from ports.knowledge_extractor import KnowledgeExtractor
from ports.llm_client import LLMClient
from synthetic.generator import TraitLibrary


def _cluster_guide_from_library(lib: TraitLibrary) -> ClusterGuide:
    """从 TraitLibrary 派生 prompt 用的 cluster_guide。

    每个簇取前 3 个 entity 作示例 —— 给 LLM 看粒度，不必全列。
    """
    guide: ClusterGuide = {}
    for cid, cluster in lib.clusters.items():
        examples = lib.cluster_entities.get(cid, [])[:3]
        guide[cid] = (cluster.name, examples)
    return guide


def _normalize_context_from_library(lib: TraitLibrary) -> NormalizeContext:
    """从 TraitLibrary 派生归一化用的 NormalizeContext。"""
    entity_to_cluster: dict[str, tuple[str, str]] = {}
    for cid, entities in lib.cluster_entities.items():
        relation = lib.cluster_relation[cid]
        for ent in entities:
            entity_to_cluster[ent] = (cid, relation)
    return NormalizeContext(
        valid_clusters=set(lib.clusters.keys()),
        entity_to_cluster=entity_to_cluster,
        entity_aliases={},  # POC 阶段先空着，未来积累同义词表
    )


def _extract_json_block(text: str) -> dict | None:
    """容错地从 LLM 输出里抠出 JSON。

    LLM 可能在 JSON 前后加解说文字。找第一个 '{' 到最后一个 '}'。
    解析失败返回 None。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except (json.JSONDecodeError, ValueError):
        return None


class ClaudeKnowledgeExtractor(KnowledgeExtractor):
    def __init__(self, llm: LLMClient,
                 library: TraitLibrary | None = None) -> None:
        self._llm = llm
        lib = library or TraitLibrary.default()
        self._cluster_guide = _cluster_guide_from_library(lib)
        self._normalize_ctx = _normalize_context_from_library(lib)

    def extract(self, text: str, persona_id: str,
                name: str, gender: str = "",
                call_point: str | None = None) -> Persona:
        del call_point  # ClaudeKnowledgeExtractor 单档,不路由
        # 1. 构建 prompt（领域逻辑）
        prompt = build_extraction_prompt(text, self._cluster_guide)

        # 2. 调 LLM（注入的 adapter）
        raw_output = self._llm.complete(prompt)

        # 3. 容错解析 JSON
        parsed = _extract_json_block(raw_output)
        raw_edges = parsed.get("edges", []) if parsed else []

        # 4. 归一化（领域逻辑）—— 脏数据进不了图
        edges = normalize_edges(raw_edges, self._normalize_ctx)

        return Persona(id=persona_id, name=name,
                       edges=tuple(edges), gender=gender, archetype="")
