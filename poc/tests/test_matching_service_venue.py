"""MatchingService.suggest_venue 集成测试。

行为契约:
  suggest_venue(result) -> str
  - 用注入的 VenueSuggester 生成场地建议
  - 不要求 result 必须 matched=True (caller 决定要不要叫;但
    我们要测出"未匹配也能调,因为没有禁止信号")
  - 没注入 VenueSuggester 时调用应抛 RuntimeError
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from adapters.fake_llm import FakeLLM
from adapters.json_persona_repository import JsonPersonaRepository
from adapters.routed_venue_suggester import RoutedVenueSuggester
from adapters.stub_narrator import StubNarrator
from adapters.stub_venue_suggester import StubVenueSuggester
from adapters.tiered_llm_factory import TieredLLMFactory
from app.matching_service import MatchingService
from domain.routing import (
    CallPoint,
    DEFAULT_ROUTING,
    LLMRouter,
    ModelTier,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _service_with_venue(suggester=None):
    repo = JsonPersonaRepository(DATA_DIR)
    return MatchingService(
        repo, StubNarrator(),
        venue_suggester=suggester,
    )


class TestSuggestVenue:
    def test_calls_injected_suggester(self):
        svc = _service_with_venue(StubVenueSuggester())
        result = svc.find_matches_for("P1")[0]
        out = svc.suggest_venue(result)
        assert isinstance(out, str) and len(out) > 0

    def test_routed_suggester_uses_haiku(self):
        haiku = FakeLLM(canned_response="一个安静的小店。")
        sonnet = FakeLLM(canned_response="x")
        opus = FakeLLM(canned_response="x")
        router = LLMRouter(DEFAULT_ROUTING)
        factory = TieredLLMFactory({
            ModelTier.HAIKU: haiku,
            ModelTier.SONNET: sonnet,
            ModelTier.OPUS: opus,
        })
        suggester = RoutedVenueSuggester(router=router, factory=factory)

        svc = _service_with_venue(suggester)
        result = svc.find_matches_for("P1")[0]
        out = svc.suggest_venue(result)

        assert out == "一个安静的小店。"
        assert haiku.call_count == 1
        assert sonnet.call_count == 0

    def test_no_suggester_raises_helpful_error(self):
        svc = _service_with_venue(suggester=None)
        result = svc.find_matches_for("P1")[0]
        with pytest.raises(RuntimeError, match="venue_suggester"):
            svc.suggest_venue(result)
