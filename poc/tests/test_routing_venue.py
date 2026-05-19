"""Tests for VENUE_SUGGEST call point —— 新增的第六个 token 调用点。

场地推荐用 Haiku (便宜,文本生成对模型质量要求中等),路由表里加这一项。
"""
from __future__ import annotations

from domain.routing import (
    CallPoint,
    DEFAULT_ROUTING,
    LLMRouter,
    ModelTier,
)


class TestVenueCallPoint:
    def test_call_point_exists(self):
        assert hasattr(CallPoint, "VENUE_SUGGEST")
        assert CallPoint.VENUE_SUGGEST != ""

    def test_default_routing_uses_haiku(self):
        """场地推荐不该烧 Sonnet —— 它不是相遇核心。"""
        router = LLMRouter(DEFAULT_ROUTING)
        assert router.tier_for(CallPoint.VENUE_SUGGEST) == ModelTier.HAIKU
