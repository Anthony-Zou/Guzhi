"""端到端测试 — 完整链路：自述文本 -> 抽取 -> 匹配 -> 推演。

这是 POC 的"全链路验收"：把 KG-First 架构的每一环都串起来跑一遍。
全程用 FakeLLM + 内存 repo，可重复、零成本、零网络。

链路：
  文本 --[ClaudeKnowledgeExtractor]--> Persona（带 KG 边）
       --[match 引擎]--> MatchResult
       --[extract_seeds]--> 故事种子
       --[ClaudeNarrator]--> 相遇对话
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Persona
from adapters.fake_llm import FakeLLM
from adapters.claude_extractor import ClaudeKnowledgeExtractor
from adapters.claude_narrator import ClaudeNarrator
from adapters.in_memory_repository import InMemoryPersonaRepository
from app.matching_service import MatchingService
from synthetic.generator import TraitLibrary


LIB = TraitLibrary.default()


def _extraction_llm(edges_payload):
    return FakeLLM(canned_response=json.dumps({"edges": edges_payload}))


def test_register_from_text_then_find_match_then_narrate():
    """完整链路跑通：两个人从文本注册，匹配上，能推演出对话。"""
    # --- 1. 两个人的自述文本 ---
    # 两人都在"去留之惑"(S1) 和 "反效率主义"(S5) 上有共鸣 -> 该匹配。
    # 用 【标记】 区分两个人 —— responder 不能靠簇 entity 名区分，
    # 因为那些词会出现在抽取 prompt 的"簇说明"部分（两人 prompt 里都有）。
    text_a = "【林知的自述】我最近一直在想要不要回老家。我也觉得人不该被KPI量化。"
    text_b = "【周临的自述】我常想留下还是离开。我相信效率不是最高价值。"

    # --- 2. 抽取器：FakeLLM 按文本标记返回对应的边 ---
    def extract_responder(prompt):
        if "【林知的自述】" in prompt:
            return json.dumps({"edges": [
                {"relation": "FEELS_NOW", "entity": "要不要回老家",
                 "strength": 0.85, "cluster": "S1", "evidence": "想回老家"},
                {"relation": "BELIEVES", "entity": "人不该被KPI量化",
                 "strength": 0.8, "cluster": "S5", "evidence": "不该被KPI量化"},
            ]})
        # 【周临的自述】
        return json.dumps({"edges": [
            {"relation": "FEELS_NOW", "entity": "留下还是离开",
             "strength": 0.85, "cluster": "S1", "evidence": "留下还是离开"},
            {"relation": "BELIEVES", "entity": "效率不是最高价值",
             "strength": 0.8, "cluster": "S5", "evidence": "效率不是最高价值"},
        ]})

    extractor = ClaudeKnowledgeExtractor(
        FakeLLM(responder=extract_responder), LIB)

    persona_a = extractor.extract(text_a, "U01", "林知", "male")
    persona_b = extractor.extract(text_b, "U02", "周临", "female")

    # 抽取出来的是带边的 Persona
    assert len(persona_a.edges) == 2
    assert len(persona_b.edges) == 2
    assert "S1" in persona_a.clusters_present()
    assert "S5" in persona_b.clusters_present()

    # --- 3. 放进内存 repo ---
    repo = InMemoryPersonaRepository(
        personas=[persona_a, persona_b],
        clusters=LIB.clusters,
        tension_pairs=LIB.tension_pairs,
        style_complement_pairs=LIB.style_complement_pairs,
    )

    # --- 4. 匹配 ---
    narrator = ClaudeNarrator(FakeLLM(
        canned_response="林知：你也常一个人来这？\n周临：嗯。\n林知：……我也是。"))
    service = MatchingService(repo, narrator)

    matches = service.find_matches_for("U01")
    assert len(matches) == 1, "两人共享 S1+S5，应该匹配上"
    assert matches[0].persona_b == "U02"

    # --- 5. 推演 ---
    story = service.narrate_match(matches[0])
    assert isinstance(story, str)
    assert len(story) > 0
    assert "林知" in story


def test_register_from_text_unmatched_pair():
    """两个文本毫无共鸣 -> 抽取后匹配为空。"""
    # 注意：抽取 prompt 里会列出所有簇的示例 entity，所以 responder 不能
    # 靠"簇 entity 名"来区分两个人 —— 那些词在两个人的 prompt 里都出现。
    # 必须靠"用户自述文本里独有的标记词"来区分。
    TEXT_A = "【甲的自述】我想回老家"
    TEXT_B = "【乙的自述】我爱攀岩"

    def extract_responder(prompt):
        if "【甲的自述】" in prompt:
            return json.dumps({"edges": [
                {"relation": "FEELS_NOW", "entity": "要不要回老家",
                 "strength": 0.85, "cluster": "S1", "evidence": "x"},
            ]})
        return json.dumps({"edges": [
            {"relation": "LIKES", "entity": "攀岩",
             "strength": 0.8, "cluster": "S11", "evidence": "y"},
        ]})

    extractor = ClaudeKnowledgeExtractor(
        FakeLLM(responder=extract_responder), LIB)
    pa = extractor.extract(TEXT_A, "U01", "甲", "male")
    pb = extractor.extract(TEXT_B, "U02", "乙", "female")

    repo = InMemoryPersonaRepository(
        personas=[pa, pb],
        clusters=LIB.clusters,
        tension_pairs=LIB.tension_pairs,
        style_complement_pairs=LIB.style_complement_pairs,
    )
    narrator = ClaudeNarrator(FakeLLM(canned_response="x"))
    service = MatchingService(repo, narrator)

    # 一个 S1 一个 S11，零共簇 -> 不匹配
    assert service.find_matches_for("U01") == []


def test_service_register_persona_from_text():
    """MatchingService 应能直接用 extractor 注册新人物（一步到位）。"""
    payload = [
        {"relation": "FEELS_NOW", "entity": "要不要回老家",
         "strength": 0.85, "cluster": "S1", "evidence": "x"},
    ]
    extractor = ClaudeKnowledgeExtractor(_extraction_llm(payload), LIB)

    repo = InMemoryPersonaRepository(
        personas=[],
        clusters=LIB.clusters,
        tension_pairs=LIB.tension_pairs,
        style_complement_pairs=LIB.style_complement_pairs,
    )
    narrator = ClaudeNarrator(FakeLLM(canned_response="x"))
    service = MatchingService(repo, narrator, extractor=extractor)

    p = service.register_from_text("我想回老家", "U01", "小明", "male")
    assert isinstance(p, Persona)
    assert p.id == "U01"
    # 注册后 repo 里能查到
    assert repo.get("U01").name == "小明"
