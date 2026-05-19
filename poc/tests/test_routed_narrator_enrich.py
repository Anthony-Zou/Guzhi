"""Tests for RoutedNarrator 的"按 tier enrich"分层策略。

策略:
  NORMAL (Haiku) ......... 不 enrich,prompt 保持原状
  HIGH_SCORE (Sonnet) .... enrich 上限 K_HIGH=3 条
  L3_PEAK (Opus) ......... enrich 上限 K_PEAK=6 条

实现路径: RoutedNarrator 自己调 select_supporting_edges (注入 repo /
cluster catalog) 并把 supporting_edges 传给 build_narration_prompt。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.fake_llm import FakeLLM
from adapters.json_persona_repository import JsonPersonaRepository
from adapters.routed_narrator import RoutedNarrator
from adapters.tiered_llm_factory import TieredLLMFactory
from domain.routing import (
    CallPoint,
    DEFAULT_ROUTING,
    LLMRouter,
    ModelTier,
)
from domain.seeds import StorySeed

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _seed():
    return StorySeed(
        seed_type="RESONANCE", cluster="C1", weight=1.0,
        a_entity="回老家", b_entity="回老家",
        a_evidence="一直在想要不要回成都", b_evidence="也想过回",
    )


def _build_routed_with_data():
    """返回 (narrator, haiku, sonnet, opus, p1, p2, shared_clusters)。"""
    repo = JsonPersonaRepository(DATA_DIR)
    haiku = FakeLLM(canned_response="h")
    sonnet = FakeLLM(canned_response="s")
    opus = FakeLLM(canned_response="o")
    router = LLMRouter(DEFAULT_ROUTING)
    factory = TieredLLMFactory({
        ModelTier.HAIKU: haiku,
        ModelTier.SONNET: sonnet,
        ModelTier.OPUS: opus,
    })
    narrator = RoutedNarrator(
        router=router, factory=factory,
        repo=repo,  # 新参数
    )
    p1 = repo.get("P1")
    p2 = repo.get("P2")
    return narrator, haiku, sonnet, opus, p1, p2


class TestEnrichmentDispatch:
    def test_haiku_call_has_no_enrich(self):
        nar, haiku, _, _, p1, p2 = _build_routed_with_data()
        nar.narrate(_seed(), p1, p2,
                    call_point=CallPoint.NORMAL_MEETING_NARRATE,
                    scene_seed=42, shared_clusters=("C1",))
        # haiku prompt 里不应该有"其他心事"块
        prompt = haiku.received_prompts[0]
        assert "其他心事" not in prompt

    def test_sonnet_call_has_enrich(self):
        nar, _, sonnet, _, p1, p2 = _build_routed_with_data()
        nar.narrate(_seed(), p1, p2,
                    call_point=CallPoint.HIGH_SCORE_MEETING_NARRATE,
                    scene_seed=42, shared_clusters=("C1",))
        prompt = sonnet.received_prompts[0]
        # P1/P2 在 C1 簇里有不止 "要不要回老家" 一条边 —— enrich 应当带出别的
        assert "其他心事" in prompt

    def test_opus_call_has_enrich_with_more_edges(self):
        nar, _, sonnet, opus, p1, p2 = _build_routed_with_data()
        # 同一对相遇,先 Sonnet 再 Opus
        nar.narrate(_seed(), p1, p2,
                    call_point=CallPoint.HIGH_SCORE_MEETING_NARRATE,
                    scene_seed=42, shared_clusters=("C1", "C2"))
        nar.narrate(_seed(), p1, p2,
                    call_point=CallPoint.L3_PEAK_MEETING_NARRATE,
                    scene_seed=42, shared_clusters=("C1", "C2"))

        sonnet_prompt = sonnet.received_prompts[0]
        opus_prompt = opus.received_prompts[0]
        # 两个都应有 enrich
        assert "其他心事" in sonnet_prompt
        assert "其他心事" in opus_prompt
        # Opus 的 enrich 区段不该比 Sonnet 短
        sonnet_enrich = sonnet_prompt[sonnet_prompt.index("其他心事"):]
        opus_enrich = opus_prompt[opus_prompt.index("其他心事"):]
        assert len(opus_enrich) >= len(sonnet_enrich)


class TestBackwardCompatNoSharedClusters:
    def test_no_shared_clusters_arg_means_no_enrich(self):
        """老 caller 不传 shared_clusters 时,enrich 段不出现 (无信息可填)。
        这保证旧测试和小镇 demo 不受影响。"""
        nar, _, sonnet, _, p1, p2 = _build_routed_with_data()
        nar.narrate(_seed(), p1, p2,
                    call_point=CallPoint.HIGH_SCORE_MEETING_NARRATE,
                    scene_seed=42)
        prompt = sonnet.received_prompts[0]
        assert "其他心事" not in prompt
