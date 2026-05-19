"""Tests for adapters.tiered_llm_factory ——
   tier (域层概念) → 真正的 LLMClient 实例 (基础设施)。

设计意图:
- domain.routing.LLMRouter 告诉我们"这个 call point 走哪一档"。
- adapter 层负责把"档"翻译成"真正能调的客户端"。
- 这两层不应该耦合 —— 路由表里不出现"具体哪个模型 ID",
  factory 里不知道"路由规则是什么"。
"""
from __future__ import annotations

import pytest

from adapters.fake_llm import FakeLLM
from adapters.tiered_llm_factory import TieredLLMFactory
from domain.routing import (
    CallPoint,
    ModelTier,
    LLMRouter,
    DEFAULT_ROUTING,
)


class TestTieredLLMFactory:
    def test_returns_client_for_each_tier(self):
        """每档对应一个 LLMClient 实例。"""
        haiku = FakeLLM(canned_response="haiku")
        sonnet = FakeLLM(canned_response="sonnet")
        opus = FakeLLM(canned_response="opus")

        factory = TieredLLMFactory({
            ModelTier.HAIKU: haiku,
            ModelTier.SONNET: sonnet,
            ModelTier.OPUS: opus,
        })

        assert factory.client_for(ModelTier.HAIKU) is haiku
        assert factory.client_for(ModelTier.SONNET) is sonnet
        assert factory.client_for(ModelTier.OPUS) is opus

    def test_unknown_tier_raises(self):
        factory = TieredLLMFactory({
            ModelTier.HAIKU: FakeLLM(canned_response="x"),
        })
        with pytest.raises(KeyError):
            factory.client_for(ModelTier.SONNET)


# ────────────────────────────────────────────────────────────────────
# 集成: router + factory 一起,描述完整的"call point → client"链路。
# ────────────────────────────────────────────────────────────────────
class TestRouterPlusFactoryIntegration:
    """这是 composition root 真正会用的组合方式。"""

    def test_call_point_resolves_to_correct_client(self):
        haiku = FakeLLM(canned_response="from haiku")
        sonnet = FakeLLM(canned_response="from sonnet")
        opus = FakeLLM(canned_response="from opus")

        router = LLMRouter(DEFAULT_ROUTING)
        factory = TieredLLMFactory({
            ModelTier.HAIKU: haiku,
            ModelTier.SONNET: sonnet,
            ModelTier.OPUS: opus,
        })

        def resolve(call_point: str):
            return factory.client_for(router.tier_for(call_point))

        # 默认路由的预期:
        assert resolve(CallPoint.ONBOARDING_EXTRACT) is sonnet
        assert resolve(CallPoint.DAILY_FEED_EXTRACT) is haiku
        assert resolve(CallPoint.NORMAL_MEETING_NARRATE) is haiku
        assert resolve(CallPoint.HIGH_SCORE_MEETING_NARRATE) is sonnet
        assert resolve(CallPoint.L3_PEAK_MEETING_NARRATE) is opus

    def test_resolved_client_actually_works(self):
        """resolve 出来的 client 真能 complete()。"""
        sonnet = FakeLLM(canned_response="sonnet says hi")
        haiku = FakeLLM(canned_response="haiku says hi")
        opus = FakeLLM(canned_response="opus says hi")

        router = LLMRouter(DEFAULT_ROUTING)
        factory = TieredLLMFactory({
            ModelTier.HAIKU: haiku,
            ModelTier.SONNET: sonnet,
            ModelTier.OPUS: opus,
        })

        client = factory.client_for(
            router.tier_for(CallPoint.L3_PEAK_MEETING_NARRATE)
        )
        assert client.complete("prompt") == "opus says hi"
