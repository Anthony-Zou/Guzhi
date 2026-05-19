"""adapter —— RoutedNarrator。

实现 Narrator 端口,内部按 call_point 路由到三档 LLM。
高档调用还会做 RAG enrich (从共簇里挑补充边塞 prompt)。

策略:
  NORMAL (Haiku) ......... 不 enrich,保留 ~300 token 的精简版
  HIGH_SCORE (Sonnet) .... enrich 上限 K_HIGH 条 (~3)
  L3_PEAK (Opus) ......... enrich 上限 K_PEAK 条 (~6)
"""
from __future__ import annotations

from domain.models import Persona
from domain.seeds import StorySeed
from domain.narration_prompt import build_narration_prompt
from domain.routing import CallPoint, LLMRouter
from domain.supporting_edges import select_supporting_edges
from ports.narrator import Narrator
from ports.persona_repository import PersonaRepository
from adapters.tiered_llm_factory import TieredLLMFactory


_NARRATE_CALL_POINTS = {
    CallPoint.NORMAL_MEETING_NARRATE,
    CallPoint.HIGH_SCORE_MEETING_NARRATE,
    CallPoint.L3_PEAK_MEETING_NARRATE,
}

# 每档允许多少条补充边
_K_PER_CALL_POINT = {
    CallPoint.NORMAL_MEETING_NARRATE: 0,
    CallPoint.HIGH_SCORE_MEETING_NARRATE: 3,
    CallPoint.L3_PEAK_MEETING_NARRATE: 6,
}


class RoutedNarrator(Narrator):
    def __init__(self, router: LLMRouter, factory: TieredLLMFactory,
                 repo: PersonaRepository | None = None) -> None:
        """repo 是可选的:不传 -> 不做 enrich (退化为'只路由不增强')。
        测试 / 老 caller 不传 repo 也能用。"""
        self._router = router
        self._factory = factory
        self._repo = repo
        # 如果有 repo,提前缓存 cluster catalog (enrich 需要)
        self._clusters = repo.clusters() if repo is not None else {}

    def narrate(self, seed: StorySeed, a: Persona, b: Persona,
                call_point: str | None = None,
                shared_clusters: tuple[str, ...] | None = None,
                scene_seed: int | None = None) -> str:
        # 默认 NORMAL —— 向后兼容
        cp = call_point or CallPoint.NORMAL_MEETING_NARRATE

        if cp not in _NARRATE_CALL_POINTS:
            raise ValueError(
                f"RoutedNarrator 只接受 narrate 类的 call point,得到 {cp!r}。"
                "抽取请用 RoutedExtractor。"
            )

        # 决定要塞多少条 supporting edges
        k = _K_PER_CALL_POINT.get(cp, 0)
        supporting = []
        if k > 0 and shared_clusters and self._clusters:
            # seed 已经占了 a_entity / b_entity,enrich 时排除避免重复
            exclude = {seed.a_entity, seed.b_entity}
            supporting = select_supporting_edges(
                a, b,
                shared_clusters=shared_clusters,
                clusters=self._clusters,
                exclude_entities=exclude,
                k=k,
            )

        tier = self._router.tier_for(cp)
        llm = self._factory.client_for(tier)

        prompt = build_narration_prompt(
            seed, a, b,
            scene_seed=scene_seed,
            supporting_edges=supporting,
        )
        return llm.complete(prompt)
