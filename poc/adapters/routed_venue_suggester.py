"""adapter —— RoutedVenueSuggester。

实现 VenueSuggester 端口,按 call point 路由到对应 tier 的 LLM。
默认 VENUE_SUGGEST -> Haiku (便宜)。
"""
from __future__ import annotations

from domain.models import Persona
from domain.routing import CallPoint, LLMRouter
from domain.shared_likes import compute_shared_likes
from domain.venue_prompt import build_venue_prompt
from ports.venue_suggester import VenueSuggester
from adapters.tiered_llm_factory import TieredLLMFactory


_ALLOWED_CALL_POINTS = {CallPoint.VENUE_SUGGEST}


class RoutedVenueSuggester(VenueSuggester):
    def __init__(self, router: LLMRouter, factory: TieredLLMFactory) -> None:
        self._router = router
        self._factory = factory

    def suggest(self, a: Persona, b: Persona,
                call_point: str | None = None) -> str:
        cp = call_point or CallPoint.VENUE_SUGGEST
        if cp not in _ALLOWED_CALL_POINTS:
            raise ValueError(
                f"RoutedVenueSuggester 只接受 VENUE_SUGGEST,得到 {cp!r}。"
                "narrate 请用 RoutedNarrator,extract 请用 RoutedExtractor。"
            )
        tier = self._router.tier_for(cp)
        llm = self._factory.client_for(tier)

        shared = compute_shared_likes(a, b)
        prompt = build_venue_prompt(a, b, shared_likes=shared)
        return llm.complete(prompt)
