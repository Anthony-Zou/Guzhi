"""Tests for adapters.routed_extractor —— 多档分层 extractor。

行为契约:
- 接收 call_point 提示 -> 按 router 选 tier -> 用对应 LLMClient 抽取。
- ONBOARDING_EXTRACT 默认走 Sonnet (KG 起点质量重要)
- DAILY_FEED_EXTRACT 默认走 Haiku (增量短文本)
- 不传 call_point 默认按 ONBOARDING_EXTRACT (保守:第一次抽用最好的)
- 三档共用同一个 prompt 模板和归一化逻辑 —— 只换模型,不换流程。
- 传入 narrate 类 call point 应当报错 (走错了端口)。
"""
from __future__ import annotations

import json

import pytest

from adapters.fake_llm import FakeLLM
from adapters.routed_extractor import RoutedKnowledgeExtractor
from adapters.tiered_llm_factory import TieredLLMFactory
from domain.routing import (
    CallPoint,
    ModelTier,
    LLMRouter,
    DEFAULT_ROUTING,
)


def _dummy_extract_response() -> str:
    """LLM 输出的 JSON 格式抽取结果。具体内容不重要,只要能被解析。"""
    return json.dumps({"edges": []})


def _build(haiku, sonnet, opus):
    router = LLMRouter(DEFAULT_ROUTING)
    factory = TieredLLMFactory({
        ModelTier.HAIKU: haiku,
        ModelTier.SONNET: sonnet,
        ModelTier.OPUS: opus,
    })
    return RoutedKnowledgeExtractor(router=router, factory=factory)


class TestRoutedExtractorDispatch:
    def test_onboarding_uses_sonnet(self):
        haiku = FakeLLM(canned_response=_dummy_extract_response())
        sonnet = FakeLLM(canned_response=_dummy_extract_response())
        opus = FakeLLM(canned_response=_dummy_extract_response())
        ex = _build(haiku, sonnet, opus)

        ex.extract("我最近一直在想……", "U1", "测试者",
                   call_point=CallPoint.ONBOARDING_EXTRACT)

        assert sonnet.call_count == 1
        assert haiku.call_count == 0

    def test_daily_feed_uses_haiku(self):
        haiku = FakeLLM(canned_response=_dummy_extract_response())
        sonnet = FakeLLM(canned_response=_dummy_extract_response())
        opus = FakeLLM(canned_response=_dummy_extract_response())
        ex = _build(haiku, sonnet, opus)

        ex.extract("听了一首歌", "U1", "测试者",
                   call_point=CallPoint.DAILY_FEED_EXTRACT)

        assert haiku.call_count == 1
        assert sonnet.call_count == 0


class TestRoutedExtractorDefault:
    def test_no_call_point_defaults_to_onboarding(self):
        """不传 call_point 默认按 onboarding 走 —— 第一次抽用最好的档。"""
        haiku = FakeLLM(canned_response=_dummy_extract_response())
        sonnet = FakeLLM(canned_response=_dummy_extract_response())
        opus = FakeLLM(canned_response=_dummy_extract_response())
        ex = _build(haiku, sonnet, opus)

        ex.extract("文本", "U1", "测试者")

        assert sonnet.call_count == 1


class TestRoutedExtractorRejectsNarrateCallPoints:
    def test_narrate_call_point_raises(self):
        ex = _build(
            FakeLLM(canned_response=_dummy_extract_response()),
            FakeLLM(canned_response=_dummy_extract_response()),
            FakeLLM(canned_response=_dummy_extract_response()),
        )
        with pytest.raises(ValueError):
            ex.extract("文本", "U1", "测试者",
                       call_point=CallPoint.NORMAL_MEETING_NARRATE)
