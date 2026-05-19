"""adapter —— ClaudeVenueSuggester。

实现 VenueSuggester 端口。组合:
  - domain.shared_likes.compute_shared_likes  (算两人共同 LIKES)
  - domain.venue_prompt.build_venue_prompt    (构 prompt)
  - LLMClient                                  (调真 LLM,注入)
"""
from __future__ import annotations

from domain.models import Persona
from domain.shared_likes import compute_shared_likes
from domain.venue_prompt import build_venue_prompt
from ports.llm_client import LLMClient
from ports.venue_suggester import VenueSuggester


class ClaudeVenueSuggester(VenueSuggester):
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def suggest(self, a: Persona, b: Persona,
                call_point: str | None = None) -> str:
        del call_point   # 单档实现,不路由
        shared = compute_shared_likes(a, b)
        prompt = build_venue_prompt(a, b, shared_likes=shared)
        return self._llm.complete(prompt)
