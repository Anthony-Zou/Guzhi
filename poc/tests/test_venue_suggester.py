"""Tests for VenueSuggester 端口的 3 个实现。

Stub: 不调 LLM,直接拼一段确定性文本。
Claude: 调注入的 LLMClient。
Routed: 用 LLMRouter 选 tier,默认走 Haiku (call point = VENUE_SUGGEST)。
"""
from __future__ import annotations

import pytest

from adapters.fake_llm import FakeLLM
from adapters.claude_venue_suggester import ClaudeVenueSuggester
from adapters.routed_venue_suggester import RoutedVenueSuggester
from adapters.stub_venue_suggester import StubVenueSuggester
from adapters.tiered_llm_factory import TieredLLMFactory
from domain.models import Edge, Persona
from domain.routing import (
    CallPoint,
    DEFAULT_ROUTING,
    LLMRouter,
    ModelTier,
)


def _p(name, likes=()):
    edges = tuple(
        Edge(relation="LIKES", entity=e, strength=0.8,
             cluster="C7", evidence=f"原话:喜欢{e}")
        for e in likes
    )
    return Persona(id=name, name=name, gender="", archetype="", edges=edges)


class TestStub:
    def test_returns_text_with_names(self):
        s = StubVenueSuggester()
        out = s.suggest(_p("林知", ["日料"]), _p("周临", ["日料"]))
        assert "林知" in out
        assert "周临" in out

    def test_lists_shared_likes_when_present(self):
        s = StubVenueSuggester()
        out = s.suggest(_p("A", ["独立书店"]), _p("B", ["独立书店"]))
        assert "独立书店" in out

    def test_no_shared_likes_returns_fallback(self):
        s = StubVenueSuggester()
        out = s.suggest(_p("A", ["山"]), _p("B", ["海"]))
        assert "林" not in out  # 不该硬推地点
        # 含兜底语
        assert "随便" in out or "其他" in out or "暂" in out or "都可以" in out


class TestClaudeWithFakeLLM:
    def test_calls_llm_with_built_prompt(self):
        llm = FakeLLM(canned_response="一段安静的建议。")
        s = ClaudeVenueSuggester(llm=llm)
        out = s.suggest(_p("林知", ["日料"]), _p("周临", ["日料"]))
        assert out == "一段安静的建议。"
        # prompt 里应该含名字和共同点
        prompt = llm.received_prompts[0]
        assert "林知" in prompt
        assert "周临" in prompt
        assert "日料" in prompt


class TestRouted:
    def _build(self):
        haiku = FakeLLM(canned_response="haiku-said")
        sonnet = FakeLLM(canned_response="sonnet-said")
        opus = FakeLLM(canned_response="opus-said")
        router = LLMRouter(DEFAULT_ROUTING)
        factory = TieredLLMFactory({
            ModelTier.HAIKU: haiku,
            ModelTier.SONNET: sonnet,
            ModelTier.OPUS: opus,
        })
        return RoutedVenueSuggester(router=router, factory=factory), haiku, sonnet, opus

    def test_default_route_uses_haiku(self):
        s, haiku, sonnet, opus = self._build()
        out = s.suggest(_p("林知", ["日料"]), _p("周临", ["日料"]))
        assert out == "haiku-said"
        assert haiku.call_count == 1
        assert sonnet.call_count == 0
        assert opus.call_count == 0

    def test_explicit_call_point(self):
        s, haiku, _, _ = self._build()
        s.suggest(_p("A", ["X"]), _p("B", ["X"]),
                  call_point=CallPoint.VENUE_SUGGEST)
        assert haiku.call_count == 1

    def test_rejects_non_venue_call_point(self):
        s, _, _, _ = self._build()
        with pytest.raises(ValueError):
            s.suggest(_p("A", ["X"]), _p("B", ["X"]),
                      call_point=CallPoint.NORMAL_MEETING_NARRATE)
