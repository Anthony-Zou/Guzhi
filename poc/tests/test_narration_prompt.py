"""TDD — 推演 prompt 构建测试（domain 层纯函数）。

build_narration_prompt：故事种子 + 两个人 -> prompt 字符串。
这是领域逻辑：prompt 的"设计"是领域知识（红线约束、场景、反例），
不依赖任何 IO，所以放 domain 层。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona
from domain.seeds import StorySeed
from domain.narration_prompt import build_narration_prompt, SCENE_POOL


def _persona(pid, name, *style_tags):
    edges = tuple(
        Edge("SPEAKS_AS", t, 0.8, None, "x") for t in style_tags
    )
    return Persona(id=pid, name=name, edges=edges)


SEED = StorySeed(
    seed_type="SHARED_CLUSTER",
    cluster="S1",
    a_entity="要不要回老家",
    b_entity="留下还是离开",
    a_evidence="最近一直在想要不要回成都老家",
    b_evidence="常想，留下还是离开",
    weight=0.8,
)


def test_prompt_contains_both_evidences():
    """prompt 里必须带双方的 evidence 原话 —— 这是 AI 写对话的原料。"""
    a = _persona("P1", "林知", "冷面笑匠")
    b = _persona("P2", "周临", "直球简洁")
    prompt = build_narration_prompt(SEED, a, b)
    assert "最近一直在想要不要回成都老家" in prompt
    assert "常想，留下还是离开" in prompt


def test_prompt_contains_both_names():
    a = _persona("P1", "林知", "冷面笑匠")
    b = _persona("P2", "周临", "直球简洁")
    prompt = build_narration_prompt(SEED, a, b)
    assert "林知" in prompt
    assert "周临" in prompt


def test_prompt_contains_style_tags():
    """双方的说话风格要进 prompt —— AI 才能写得像他们。"""
    a = _persona("P1", "林知", "冷面笑匠", "自嘲式幽默")
    b = _persona("P2", "周临", "直球简洁")
    prompt = build_narration_prompt(SEED, a, b)
    assert "冷面笑匠" in prompt
    assert "自嘲式幽默" in prompt
    assert "直球简洁" in prompt


def test_prompt_contains_red_lines():
    """prompt 必须包含红线约束 —— 不准 AI 腔、不准泄露系统、不准强行收束。"""
    a = _persona("P1", "林知", "冷面笑匠")
    b = _persona("P2", "周临", "直球简洁")
    prompt = build_narration_prompt(SEED, a, b)
    # 至少这几条红线关键词要在
    assert "系统" in prompt or "算法" in prompt   # 不准提系统/算法
    assert "总结" in prompt or "收束" in prompt or "鸡汤" in prompt
    assert "编造" in prompt or "捏造" in prompt   # 不准编造 evidence 外的


def test_prompt_uses_a_scene():
    """prompt 里要带一个场景 —— 来自场景池。"""
    a = _persona("P1", "林知", "冷面笑匠")
    b = _persona("P2", "周临", "直球简洁")
    prompt = build_narration_prompt(SEED, a, b)
    assert any(scene in prompt for scene in SCENE_POOL)


def test_prompt_is_deterministic_with_scene_seed():
    """给定 scene_seed，prompt 完全确定 —— 可重复测试的前提。"""
    a = _persona("P1", "林知", "冷面笑匠")
    b = _persona("P2", "周临", "直球简洁")
    p1 = build_narration_prompt(SEED, a, b, scene_seed=7)
    p2 = build_narration_prompt(SEED, a, b, scene_seed=7)
    assert p1 == p2


def test_tension_seed_prompt_differs_from_shared():
    """对立种子和共鸣种子，prompt 的指令应该不同。"""
    a = _persona("P1", "林知", "冷面笑匠")
    b = _persona("P2", "周临", "直球简洁")
    tension_seed = StorySeed(
        seed_type="CREATIVE_TENSION",
        cluster="S10", a_entity="黑泽明", b_entity="侯孝贤",
        a_evidence="我痴迷黑泽明", b_evidence="我更喜欢侯孝贤",
        weight=1.2,
    )
    shared_prompt = build_narration_prompt(SEED, a, b, scene_seed=1)
    tension_prompt = build_narration_prompt(tension_seed, a, b, scene_seed=1)
    assert shared_prompt != tension_prompt
    # 对立种子的 prompt 应该提到"分歧"或"对立"或"不让步"
    assert ("分歧" in tension_prompt or "对立" in tension_prompt
            or "不让步" in tension_prompt or "相反" in tension_prompt)
