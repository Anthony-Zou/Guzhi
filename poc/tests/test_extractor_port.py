"""TDD — KnowledgeExtractor 端口 + StubKnowledgeExtractor 测试。

KnowledgeExtractor 是一个新端口：抽象"一段自述文本 -> 一个 Persona（带 KG 边）"。
这是规模化的必经之路 —— 真实产品不可能手工标注每个人。

POC 阶段：
  - 端口定义清楚
  - StubKnowledgeExtractor：规则式假抽取器，验证链路接通
  - ClaudeKnowledgeExtractor（下一个任务）：真用 LLM 抽，代码写全
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Persona, Edge
from ports.knowledge_extractor import KnowledgeExtractor
from adapters.stub_extractor import StubKnowledgeExtractor


def test_stub_implements_port():
    stub = StubKnowledgeExtractor()
    assert isinstance(stub, KnowledgeExtractor)


def test_extract_returns_a_persona():
    """extract 输入文本 + 身份信息，输出一个 Persona。"""
    stub = StubKnowledgeExtractor()
    p = stub.extract(
        text="我最近一直在想要不要回老家。我讨厌职场正能量。",
        persona_id="U01", name="测试用户", gender="female",
    )
    assert isinstance(p, Persona)
    assert p.id == "U01"
    assert p.name == "测试用户"
    assert p.gender == "female"


def test_extract_produces_edges():
    """抽取出的 Persona 必须有边 —— 否则没法参与匹配。"""
    stub = StubKnowledgeExtractor()
    p = stub.extract(
        text="我最近一直在想要不要回老家。我讨厌职场正能量。",
        persona_id="U01", name="测试用户", gender="female",
    )
    assert len(p.edges) > 0
    for e in p.edges:
        assert isinstance(e, Edge)


def test_stub_extracts_known_keywords():
    """Stub 抽取器靠关键词匹配 —— 文本里有'回老家'就抽出对应的边。"""
    stub = StubKnowledgeExtractor()
    p = stub.extract(
        text="我最近一直在想要不要回老家。",
        persona_id="U01", name="测试用户", gender="male",
    )
    entities = {e.entity for e in p.edges}
    assert "要不要回老家" in entities


def test_stub_returns_empty_edges_for_unmatched_text():
    """文本里没有任何已知关键词 -> 抽不出边（Persona 边为空）。

    这暴露了 stub 的局限：它只能抽预设关键词。真 LLM 不受这个限制。
    """
    stub = StubKnowledgeExtractor()
    p = stub.extract(
        text="今天天气不错，吃了个三明治。",
        persona_id="U01", name="测试用户", gender="male",
    )
    assert len(p.edges) == 0


def test_stub_is_deterministic():
    """同输入同输出 —— 可重复。"""
    stub = StubKnowledgeExtractor()
    text = "我讨厌职场正能量，最近一直在想要不要回老家。"
    p1 = stub.extract(text, "U01", "甲", "male")
    p2 = stub.extract(text, "U01", "甲", "male")
    assert [(e.relation, e.entity, e.cluster) for e in p1.edges] == \
           [(e.relation, e.entity, e.cluster) for e in p2.edges]
