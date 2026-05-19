"""TDD — 抽取 prompt 构建测试（domain 层纯函数）。

build_extraction_prompt：自述文本 + 簇定义 -> 给 LLM 的抽取 prompt。
prompt 要告诉 LLM：有哪些簇、每个簇是什么、要抽成什么 JSON 格式、
strength 怎么定、不准编造。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.extraction_prompt import build_extraction_prompt


# 简化的簇说明：cluster_id -> (簇名, 该簇下的示例 entity)
CLUSTER_GUIDE = {
    "S1": ("去留之惑", ["要不要回老家", "留下还是离开"]),
    "S5": ("反效率主义", ["人不该被KPI量化", "效率不是最高价值"]),
    "S9": ("反正能量表演", ["职场正能量", "积极心理学话术"]),
}

TEXT = "我最近一直在想要不要回老家。我特别讨厌职场正能量那一套。"


def test_prompt_contains_the_text():
    """prompt 里必须带用户的自述文本。"""
    prompt = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    assert TEXT in prompt


def test_prompt_lists_all_clusters():
    """prompt 要列出所有簇 —— LLM 才知道能往哪些簇里抽。"""
    prompt = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    for cid, (name, _) in CLUSTER_GUIDE.items():
        assert cid in prompt
        assert name in prompt


def test_prompt_includes_example_entities():
    """prompt 要给每个簇的示例 entity —— LLM 才知道粒度。"""
    prompt = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    assert "要不要回老家" in prompt
    assert "职场正能量" in prompt


def test_prompt_asks_for_json():
    """prompt 必须明确要求 JSON 输出 —— 否则没法解析。"""
    prompt = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    assert "JSON" in prompt or "json" in prompt
    # 要说明字段
    assert "relation" in prompt
    assert "entity" in prompt
    assert "strength" in prompt


def test_prompt_has_anti_fabrication_rule():
    """prompt 要有"不准编造"的约束 —— 只抽文本里真有的。"""
    prompt = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    assert "编造" in prompt or "捏造" in prompt or "文本里" in prompt


def test_prompt_explains_strength():
    """prompt 要解释 strength 怎么定（语气强 -> 高分）。"""
    prompt = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    assert "strength" in prompt
    assert "语气" in prompt or "强烈" in prompt or "0" in prompt


def test_prompt_is_deterministic():
    """同输入同 prompt。"""
    p1 = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    p2 = build_extraction_prompt(TEXT, CLUSTER_GUIDE)
    assert p1 == p2
