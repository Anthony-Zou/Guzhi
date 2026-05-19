"""adapter — AnthropicLLM。

实现 LLMClient 端口，真调 Claude API。

注意：这个 adapter 不在自动化测试里跑（需要真 API key + 网络）。
测试用 FakeLLM 代替。等你填了 ANTHROPIC_API_KEY，在 guzhi_poc.py
里把 FakeLLM 换成 AnthropicLLM 即可，领域/应用层一行都不用改。

用法：
    from adapters.anthropic_llm import AnthropicLLM
    llm = AnthropicLLM(model="claude-haiku-4-5-20251001")
    # 需要环境变量 ANTHROPIC_API_KEY
"""
from __future__ import annotations

import os

from ports.llm_client import LLMClient


class AnthropicLLM(LLMClient):
    def __init__(self,
                 model: str = "claude-haiku-4-5-20251001",
                 max_tokens: int = 1024,
                 api_key: str | None = None) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError(
                "AnthropicLLM 需要 API key：设置环境变量 ANTHROPIC_API_KEY，"
                "或在构造时传 api_key=。"
            )
        self._client = None  # 懒加载，避免没装 anthropic 包时 import 失败

    def _ensure_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError as e:
                raise RuntimeError(
                    "AnthropicLLM 需要 anthropic 包：pip install anthropic"
                ) from e
            self._client = Anthropic(api_key=self._api_key)
        return self._client

    def complete(self, prompt: str) -> str:
        client = self._ensure_client()
        resp = client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        # Claude 的响应是 content blocks，取第一个 text block
        parts = [
            block.text for block in resp.content
            if getattr(block, "type", None) == "text"
        ]
        return "".join(parts)
