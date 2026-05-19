"""adapter —— TieredLLMFactory。

把 domain.routing 给的 "ModelTier" 翻译成真正能调的 LLMClient 实例。

设计上的隔离:
- domain.routing 不知道"哪个 tier 对应哪个模型 ID / 哪个 API"。
- 这里也不知道"哪个 call point 走哪一档"。
- 中间的桥梁是 composition root (guzhi_poc.py),它把 router 和
  factory 拼起来,并且决定:这一档塞 AnthropicLLM(haiku-4-5) 还是
  AnthropicLLM(sonnet-4-6) 还是 FakeLLM (测试时)。

测试时:三档全塞 FakeLLM —— 零成本零网络。
生产时:三档塞不同 model 配置的 AnthropicLLM。
"""
from __future__ import annotations

from typing import Mapping

from ports.llm_client import LLMClient


class TieredLLMFactory:
    """tier → LLMClient 实例的查表器。"""

    def __init__(self, tier_to_client: Mapping[str, LLMClient]) -> None:
        self._clients: dict[str, LLMClient] = dict(tier_to_client)

    def client_for(self, tier: str) -> LLMClient:
        """返回该 tier 对应的 LLMClient。未配置则抛 KeyError。"""
        return self._clients[tier]

    def tiers(self) -> list[str]:
        """返回当前 factory 注册了哪些 tier。"""
        return list(self._clients.keys())
