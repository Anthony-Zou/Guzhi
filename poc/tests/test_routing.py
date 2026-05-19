"""Tests for domain.routing —— LLMRouter（决定每个 call point 走哪一档模型）。

设计意图（写在测试里好让 review 者看清）：
- LLMRouter 是域层的概念 —— "哪个 call point 用哪个 tier" 是业务决定,
  不是基础设施。所以它住在 domain/。
- Router 不持有"模型实例"的真实对象,它持有一张表:
    {CallPoint: ModelTier}
- 真正的 LLMClient 注入由调用方决定。Router 只回答："这个调用应该用哪一档?"
  然后调用方 (composition root) 从 tier -> LLMClient 的字典里取实例。
- 这样 domain 里没有任何对 anthropic SDK 的依赖。
"""
from __future__ import annotations

import pytest

from domain.routing import (
    CallPoint,
    ModelTier,
    LLMRouter,
    DEFAULT_ROUTING,
)


# ────────────────────────────────────────────────────────────────────
# 1. CallPoint 是常量 —— 调用方靠这些常量描述自己
# ────────────────────────────────────────────────────────────────────
class TestCallPoints:
    def test_all_required_call_points_exist(self):
        """五个真正消耗 token 的调用点都应该有名字。"""
        # 抽取
        assert hasattr(CallPoint, "ONBOARDING_EXTRACT")
        assert hasattr(CallPoint, "DAILY_FEED_EXTRACT")
        # 推演
        assert hasattr(CallPoint, "NORMAL_MEETING_NARRATE")
        assert hasattr(CallPoint, "HIGH_SCORE_MEETING_NARRATE")
        assert hasattr(CallPoint, "L3_PEAK_MEETING_NARRATE")


# ────────────────────────────────────────────────────────────────────
# 2. ModelTier 是三档抽象 —— router 输出的是档,不是具体模型
# ────────────────────────────────────────────────────────────────────
class TestModelTier:
    def test_three_tiers_exist(self):
        assert ModelTier.HAIKU
        assert ModelTier.SONNET
        assert ModelTier.OPUS


# ────────────────────────────────────────────────────────────────────
# 3. LLMRouter 的核心契约: 给一个 call point,返回一个 tier
# ────────────────────────────────────────────────────────────────────
class TestLLMRouter:
    def test_returns_configured_tier_for_call_point(self):
        """显式给一张路由表,router 严格照表派发。"""
        routing = {
            CallPoint.ONBOARDING_EXTRACT: ModelTier.SONNET,
            CallPoint.DAILY_FEED_EXTRACT: ModelTier.HAIKU,
        }
        router = LLMRouter(routing)
        assert router.tier_for(CallPoint.ONBOARDING_EXTRACT) == ModelTier.SONNET
        assert router.tier_for(CallPoint.DAILY_FEED_EXTRACT) == ModelTier.HAIKU

    def test_unknown_call_point_raises(self):
        """不在表里的 call point 应该报错 —— 路由必须是显式的。"""
        router = LLMRouter({})
        with pytest.raises(KeyError):
            router.tier_for(CallPoint.NORMAL_MEETING_NARRATE)


# ────────────────────────────────────────────────────────────────────
# 4. DEFAULT_ROUTING —— 默认配置反映 PHASE2_BACKLOG 的决策
# ────────────────────────────────────────────────────────────────────
class TestDefaultRouting:
    def test_onboarding_uses_sonnet(self):
        """Onboarding 决定 KG 起点质量,值得用 Sonnet。"""
        router = LLMRouter(DEFAULT_ROUTING)
        assert router.tier_for(CallPoint.ONBOARDING_EXTRACT) == ModelTier.SONNET

    def test_daily_feed_uses_haiku(self):
        """日常投喂增量小,Haiku 够。"""
        router = LLMRouter(DEFAULT_ROUTING)
        assert router.tier_for(CallPoint.DAILY_FEED_EXTRACT) == ModelTier.HAIKU

    def test_normal_meeting_uses_haiku(self):
        """大头(~75%)用 Haiku 压成本。"""
        router = LLMRouter(DEFAULT_ROUTING)
        assert router.tier_for(CallPoint.NORMAL_MEETING_NARRATE) == ModelTier.HAIKU

    def test_high_score_meeting_uses_sonnet(self):
        """高分相遇值得细腻笔触。"""
        router = LLMRouter(DEFAULT_ROUTING)
        assert router.tier_for(CallPoint.HIGH_SCORE_MEETING_NARRATE) == ModelTier.SONNET

    def test_l3_peak_meeting_uses_opus(self):
        """5% 的灵魂时刻升级到 Opus —— 不是省钱,是把钱花在刀刃上。"""
        router = LLMRouter(DEFAULT_ROUTING)
        assert router.tier_for(CallPoint.L3_PEAK_MEETING_NARRATE) == ModelTier.OPUS


# ────────────────────────────────────────────────────────────────────
# 5. tier_for 是稳定的查询 (deterministic) —— 不是真正的"决策时刻"
#    决策时刻是相遇 score 决定 NORMAL vs HIGH vs L3 —— 那在 caller 里。
# ────────────────────────────────────────────────────────────────────
class TestRouterIsPureLookup:
    def test_same_input_same_tier(self):
        router = LLMRouter(DEFAULT_ROUTING)
        first = router.tier_for(CallPoint.NORMAL_MEETING_NARRATE)
        second = router.tier_for(CallPoint.NORMAL_MEETING_NARRATE)
        assert first == second
