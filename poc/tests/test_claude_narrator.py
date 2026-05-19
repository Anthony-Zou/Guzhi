"""TDD — ClaudeNarrator 测试。

ClaudeNarrator 实现 Narrator 端口，组合 build_narration_prompt + LLMClient。
测试用 FakeLLM 注入 —— 可重复、零成本。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import Edge, Persona
from domain.seeds import StorySeed
from ports.narrator import Narrator
from adapters.fake_llm import FakeLLM
from adapters.claude_narrator import ClaudeNarrator


def _persona(pid, name, *style_tags):
    edges = tuple(Edge("SPEAKS_AS", t, 0.8, None, "x") for t in style_tags)
    return Persona(id=pid, name=name, edges=edges)


SEED = StorySeed(
    seed_type="SHARED_CLUSTER", cluster="S1",
    a_entity="要不要回老家", b_entity="留下还是离开",
    a_evidence="最近一直在想要不要回成都老家",
    b_evidence="常想，留下还是离开", weight=0.8,
)
A = _persona("P1", "林知", "冷面笑匠")
B = _persona("P2", "周临", "直球简洁")


def test_claude_narrator_implements_port():
    narrator = ClaudeNarrator(FakeLLM(canned_response="对话"))
    assert isinstance(narrator, Narrator)


def test_narrate_returns_llm_output():
    """narrate 返回的就是 LLM 的输出。"""
    fake = FakeLLM(canned_response="林知：你也常来这？\n周临：嗯。")
    narrator = ClaudeNarrator(fake)
    out = narrator.narrate(SEED, A, B)
    assert out == "林知：你也常来这？\n周临：嗯。"


def test_narrate_sends_a_proper_prompt_to_llm():
    """narrate 喂给 LLM 的 prompt 必须是构建好的推演 prompt（含 evidence、红线）。"""
    fake = FakeLLM(canned_response="x")
    narrator = ClaudeNarrator(fake)
    narrator.narrate(SEED, A, B)
    assert fake.call_count == 1
    prompt = fake.received_prompts[0]
    # prompt 里要有双方原话、名字、红线
    assert "最近一直在想要不要回成都老家" in prompt
    assert "林知" in prompt and "周临" in prompt
    assert "红线" in prompt


def test_narrate_is_deterministic_with_scene_seed():
    """给 scene_seed，同输入同 prompt（因此 FakeLLM 同输出）。"""
    fake1 = FakeLLM(canned_response="x")
    fake2 = FakeLLM(canned_response="x")
    ClaudeNarrator(fake1).narrate(SEED, A, B, scene_seed=3)
    ClaudeNarrator(fake2).narrate(SEED, A, B, scene_seed=3)
    assert fake1.received_prompts[0] == fake2.received_prompts[0]


def test_narrate_only_calls_llm_once():
    """一次推演只调一次 LLM —— 成本可控。"""
    fake = FakeLLM(canned_response="x")
    ClaudeNarrator(fake).narrate(SEED, A, B)
    assert fake.call_count == 1
