"""TDD — ClaudeKnowledgeExtractor 测试。

ClaudeKnowledgeExtractor 实现 KnowledgeExtractor 端口，组合：
  build_extraction_prompt（领域）+ LLMClient（注入）
  + JSON 解析 + normalize_edges（领域）

测试用 FakeLLM 注入，返回预设的 JSON —— 可重复、零成本。
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Persona
from ports.knowledge_extractor import KnowledgeExtractor
from adapters.fake_llm import FakeLLM
from adapters.claude_extractor import ClaudeKnowledgeExtractor
from synthetic.generator import TraitLibrary


LIB = TraitLibrary.default()


def _llm_returning(edges_payload: list[dict]) -> FakeLLM:
    """造一个返回指定 edges JSON 的 FakeLLM。"""
    return FakeLLM(canned_response=json.dumps({"edges": edges_payload}))


def test_extractor_implements_port():
    extractor = ClaudeKnowledgeExtractor(_llm_returning([]), LIB)
    assert isinstance(extractor, KnowledgeExtractor)


def test_extract_returns_persona_with_identity():
    extractor = ClaudeKnowledgeExtractor(_llm_returning([]), LIB)
    p = extractor.extract("一段文本", "U01", "小明", "male")
    assert isinstance(p, Persona)
    assert p.id == "U01"
    assert p.name == "小明"
    assert p.gender == "male"


def test_extract_parses_llm_json_into_edges():
    """LLM 返回的 JSON 边 -> 解析 + 归一化 -> Persona.edges。"""
    payload = [
        {"relation": "FEELS_NOW", "entity": "要不要回老家",
         "strength": 0.85, "cluster": "S1", "evidence": "想回老家"},
    ]
    extractor = ClaudeKnowledgeExtractor(_llm_returning(payload), LIB)
    p = extractor.extract("我想回老家", "U01", "小明")
    assert len(p.edges) == 1
    assert p.edges[0].entity == "要不要回老家"
    assert p.edges[0].cluster == "S1"


def test_extract_sends_extraction_prompt():
    """喂给 LLM 的必须是构建好的抽取 prompt（含文本、簇说明、JSON 要求）。"""
    fake = _llm_returning([])
    extractor = ClaudeKnowledgeExtractor(fake, LIB)
    extractor.extract("我最近想换城市", "U01", "小明")
    assert fake.call_count == 1
    prompt = fake.received_prompts[0]
    assert "我最近想换城市" in prompt
    assert "JSON" in prompt or "json" in prompt


def test_extract_applies_normalization():
    """LLM 返回越界 strength / 非法簇 -> 归一化生效。"""
    payload = [
        {"relation": "FEELS_NOW", "entity": "要不要回老家",
         "strength": 1.9, "cluster": "S1", "evidence": "x"},   # strength 越界
        {"relation": "LIKES", "entity": "瞎编的东西",
         "strength": 0.7, "cluster": "S999", "evidence": "y"}, # 非法簇
    ]
    extractor = ClaudeKnowledgeExtractor(_llm_returning(payload), LIB)
    p = extractor.extract("文本", "U01", "小明")
    by_entity = {e.entity: e for e in p.edges}
    # strength 被 clamp
    assert by_entity["要不要回老家"].strength == 1.0
    # 非法簇的 entity 降级为噪音边
    assert by_entity["瞎编的东西"].cluster is None


def test_extract_handles_malformed_json():
    """LLM 返回的不是合法 JSON -> 不崩，返回边为空的 Persona。"""
    fake = FakeLLM(canned_response="抱歉我不会做")
    extractor = ClaudeKnowledgeExtractor(fake, LIB)
    p = extractor.extract("文本", "U01", "小明")
    assert isinstance(p, Persona)
    assert len(p.edges) == 0


def test_extract_handles_json_wrapped_in_text():
    """LLM 在 JSON 前后加了解说文字 -> 仍能抽出 JSON。"""
    payload = {"edges": [
        {"relation": "FEELS_NOW", "entity": "要不要回老家",
         "strength": 0.8, "cluster": "S1", "evidence": "x"},
    ]}
    wrapped = f"好的，这是抽取结果：\n{json.dumps(payload)}\n希望有帮助。"
    fake = FakeLLM(canned_response=wrapped)
    extractor = ClaudeKnowledgeExtractor(fake, LIB)
    p = extractor.extract("文本", "U01", "小明")
    assert len(p.edges) == 1
