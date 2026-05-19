"""端口 — LLMClient。

抽象"调一次 LLM —— 给 prompt，拿文本回来"。

KG-First 架构里，AI 只在两个地方出现：
  1. 故事推演（Narrator）
  2. 自动抽取 KG 边（KnowledgeExtractor）
两者都不直接依赖 anthropic SDK，而是依赖这个 LLMClient 端口。

好处：
- 测试注入 FakeLLM —— 可重复、零成本、零网络
- 生产注入 AnthropicLLM —— 真调 Claude
- 换模型、换厂商，只改一个 adapter
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """一次 LLM 调用的抽象。"""

    @abstractmethod
    def complete(self, prompt: str) -> str:
        """输入一个 prompt 文本，返回 LLM 生成的文本。

        实现可以是真 Claude、假回复、或别的模型。
        领域/应用层不关心。
        """
        ...
