"""TDD — LLMClient 端口 + FakeLLM 测试。

LLMClient 是一个端口：抽象"调一次 LLM —— 给 prompt，拿文本回来"。
ClaudeNarrator 和 ClaudeKnowledgeExtractor 都依赖这个抽象，
而不是直接依赖 anthropic SDK。

为什么要这层抽象：
- 测试时注入 FakeLLM —— 可重复、零成本、不需要网络
- 生产时注入 AnthropicLLM —— 真调 Claude
- 领域/应用层完全不知道背后是真 LLM 还是假的

这就是六边形架构：AI 也被关在一个端口背后。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ports.llm_client import LLMClient
from adapters.fake_llm import FakeLLM


def test_fake_llm_implements_port():
    fake = FakeLLM(canned_response="hello")
    assert isinstance(fake, LLMClient)


def test_fake_llm_returns_canned_response():
    """最简单用法：不管 prompt 是什么，返回预设的回复。"""
    fake = FakeLLM(canned_response="一段对话")
    out = fake.complete("任意 prompt")
    assert out == "一段对话"


def test_fake_llm_records_prompts():
    """FakeLLM 记录收到过的 prompt —— 测试可以断言 prompt 内容。"""
    fake = FakeLLM(canned_response="x")
    fake.complete("prompt A")
    fake.complete("prompt B")
    assert fake.received_prompts == ["prompt A", "prompt B"]


def test_fake_llm_rule_based_response():
    """进阶用法：按 prompt 内容用规则决定回复 —— 测复杂场景用。"""
    def rule(prompt: str) -> str:
        if "推演" in prompt:
            return "对话内容"
        if "抽取" in prompt:
            return '{"edges": []}'
        return "默认"

    fake = FakeLLM(responder=rule)
    assert fake.complete("请推演") == "对话内容"
    assert fake.complete("请抽取") == '{"edges": []}'
    assert fake.complete("其他") == "默认"


def test_fake_llm_call_count():
    """FakeLLM 记录调用次数 —— 测试可以断言"只调了一次"之类。"""
    fake = FakeLLM(canned_response="x")
    assert fake.call_count == 0
    fake.complete("p1")
    fake.complete("p2")
    assert fake.call_count == 2
