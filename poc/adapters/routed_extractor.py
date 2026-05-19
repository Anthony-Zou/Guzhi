"""adapter —— RoutedKnowledgeExtractor。

实现 KnowledgeExtractor 端口,内部按 call_point 路由到三档 LLM。

设计:
- 内部持有三个 ClaudeKnowledgeExtractor (每档一个),共用同一份
  TraitLibrary 派生出的 prompt/归一化规则。
- call_point 决定 tier,tier 决定底层用哪个 ClaudeKnowledgeExtractor。
- 默认 call_point = ONBOARDING_EXTRACT (保守:第一次抽用最好的)。

为什么不像 RoutedNarrator 那样"直接调 LLM + build_prompt"?
  因为 extract 比 narrate 复杂:还有 JSON 解析 + 归一化。
  把这条 pipeline 复用 ClaudeKnowledgeExtractor 而不是重写一遍,
  符合 DRY,也免得规则飘移。
"""
from __future__ import annotations

from domain.models import Persona
from domain.routing import CallPoint, LLMRouter
from ports.knowledge_extractor import KnowledgeExtractor
from adapters.claude_extractor import ClaudeKnowledgeExtractor
from adapters.tiered_llm_factory import TieredLLMFactory
from synthetic.generator import TraitLibrary


_EXTRACT_CALL_POINTS = {
    CallPoint.ONBOARDING_EXTRACT,
    CallPoint.DAILY_FEED_EXTRACT,
}


class RoutedKnowledgeExtractor(KnowledgeExtractor):
    def __init__(self, router: LLMRouter, factory: TieredLLMFactory,
                 library: TraitLibrary | None = None) -> None:
        self._router = router
        self._factory = factory
        lib = library or TraitLibrary.default()
        # 三档各预构造一个 ClaudeKnowledgeExtractor —— 共享 lib 派生的规则,
        # 只在底层 LLMClient 上不同。
        self._extractors_by_tier: dict[str, ClaudeKnowledgeExtractor] = {}
        for tier in factory.tiers():
            llm = factory.client_for(tier)
            self._extractors_by_tier[tier] = ClaudeKnowledgeExtractor(
                llm=llm, library=lib
            )

    def extract(self, text: str, persona_id: str,
                name: str, gender: str = "",
                call_point: str | None = None) -> Persona:
        cp = call_point or CallPoint.ONBOARDING_EXTRACT

        if cp not in _EXTRACT_CALL_POINTS:
            raise ValueError(
                f"RoutedKnowledgeExtractor 只接受 extract 类的 call point,"
                f"得到 {cp!r}。推演请用 RoutedNarrator。"
            )

        tier = self._router.tier_for(cp)
        ex = self._extractors_by_tier[tier]
        return ex.extract(text, persona_id, name, gender)
