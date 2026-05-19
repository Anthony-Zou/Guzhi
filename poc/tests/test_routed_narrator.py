"""Tests for adapters.routed_narrator —— 多档分层 narrator。

集成 LLMRouter + TieredLLMFactory + ClaudeNarrator(每档一个)。

行为契约:
- 接收一个 call_point 提示 -> 根据 router 选 tier -> 用对应 tier 的
  ClaudeNarrator 推演。
- 不传 call_point 时,默认走 NORMAL_MEETING_NARRATE (最保守的一档)。
- 三档之间的 prompt 构建逻辑相同 (都用 build_narration_prompt),
  区别只在 LLM 调用。
"""
from __future__ import annotations

import pytest

from adapters.fake_llm import FakeLLM
from adapters.routed_narrator import RoutedNarrator
from adapters.tiered_llm_factory import TieredLLMFactory
from domain.models import Persona, Edge
from domain.routing import (
    CallPoint,
    ModelTier,
    LLMRouter,
    DEFAULT_ROUTING,
)
from domain.seeds import StorySeed


# ── 测试辅助 ──
def _make_persona(pid: str, name: str = "甲") -> Persona:
    return Persona(
        id=pid, name=name, gender="female",
        archetype="测试",
        edges=(Edge(relation="LIKES", entity="测试实体",
                    strength=0.8, cluster="S1", evidence="爱测试"),),
    )


def _make_seed() -> StorySeed:
    return StorySeed(
        seed_type="RESONANCE", cluster="S2", weight=1.0,
        a_entity="想躺平", b_entity="想躺平",
        a_evidence="想躺平", b_evidence="想躺平",
    )


def _build_routed(haiku, sonnet, opus, *, routing=DEFAULT_ROUTING):
    """构造一个用三档 FakeLLM 跑的 RoutedNarrator。"""
    router = LLMRouter(routing)
    factory = TieredLLMFactory({
        ModelTier.HAIKU: haiku,
        ModelTier.SONNET: sonnet,
        ModelTier.OPUS: opus,
    })
    return RoutedNarrator(router=router, factory=factory)


# ────────────────────────────────────────────────────────────────────
class TestRoutedNarratorDispatch:
    def test_normal_meeting_uses_haiku(self):
        haiku = FakeLLM(canned_response="haiku reply")
        sonnet = FakeLLM(canned_response="sonnet reply")
        opus = FakeLLM(canned_response="opus reply")
        nar = _build_routed(haiku, sonnet, opus)

        out = nar.narrate(_make_seed(), _make_persona("A"), _make_persona("B", "乙"),
                          call_point=CallPoint.NORMAL_MEETING_NARRATE)

        assert out == "haiku reply"
        assert haiku.call_count == 1
        assert sonnet.call_count == 0
        assert opus.call_count == 0

    def test_high_score_meeting_uses_sonnet(self):
        haiku = FakeLLM(canned_response="haiku reply")
        sonnet = FakeLLM(canned_response="sonnet reply")
        opus = FakeLLM(canned_response="opus reply")
        nar = _build_routed(haiku, sonnet, opus)

        out = nar.narrate(_make_seed(), _make_persona("A"), _make_persona("B", "乙"),
                          call_point=CallPoint.HIGH_SCORE_MEETING_NARRATE)

        assert out == "sonnet reply"
        assert sonnet.call_count == 1
        assert haiku.call_count == 0
        assert opus.call_count == 0

    def test_l3_peak_meeting_uses_opus(self):
        haiku = FakeLLM(canned_response="haiku reply")
        sonnet = FakeLLM(canned_response="sonnet reply")
        opus = FakeLLM(canned_response="opus reply")
        nar = _build_routed(haiku, sonnet, opus)

        out = nar.narrate(_make_seed(), _make_persona("A"), _make_persona("B", "乙"),
                          call_point=CallPoint.L3_PEAK_MEETING_NARRATE)

        assert out == "opus reply"
        assert opus.call_count == 1


class TestRoutedNarratorDefault:
    def test_no_call_point_defaults_to_normal(self):
        """不传 call_point 默认按 normal 走 —— 这条是向后兼容老代码。"""
        haiku = FakeLLM(canned_response="haiku")
        sonnet = FakeLLM(canned_response="sonnet")
        opus = FakeLLM(canned_response="opus")
        nar = _build_routed(haiku, sonnet, opus)

        nar.narrate(_make_seed(), _make_persona("A"), _make_persona("B", "乙"))

        assert haiku.call_count == 1


class TestRoutedNarratorPromptIsSame:
    """三档用的是同一个 prompt 模板 —— routing 不该改 prompt 内容,只换模型。"""

    def test_same_prompt_regardless_of_tier(self):
        haiku = FakeLLM(canned_response="x")
        sonnet = FakeLLM(canned_response="y")
        opus = FakeLLM(canned_response="z")
        nar = _build_routed(haiku, sonnet, opus)

        seed, a, b = _make_seed(), _make_persona("A"), _make_persona("B", "乙")
        # 用固定 scene_seed,确保 prompt 完全确定 —— 否则场景随机会让对比失败
        nar.narrate(seed, a, b, call_point=CallPoint.NORMAL_MEETING_NARRATE, scene_seed=42)
        nar.narrate(seed, a, b, call_point=CallPoint.HIGH_SCORE_MEETING_NARRATE, scene_seed=42)
        nar.narrate(seed, a, b, call_point=CallPoint.L3_PEAK_MEETING_NARRATE, scene_seed=42)

        # 三个 prompt 完全一致
        assert haiku.received_prompts[0] == sonnet.received_prompts[0]
        assert sonnet.received_prompts[0] == opus.received_prompts[0]


class TestRoutedNarratorRejectsExtractCallPoints:
    """RoutedNarrator 只服务 narrate 类的 call point。
    传入 extract 类 call point 应当报错 —— 它走错了端口。"""

    def test_extract_call_point_raises(self):
        nar = _build_routed(
            FakeLLM(canned_response="x"),
            FakeLLM(canned_response="x"),
            FakeLLM(canned_response="x"),
        )
        with pytest.raises(ValueError):
            nar.narrate(_make_seed(), _make_persona("A"), _make_persona("B", "乙"),
                        call_point=CallPoint.ONBOARDING_EXTRACT)
