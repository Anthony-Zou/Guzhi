"""adapter — FakeLLM。

实现 LLMClient 端口，但不真调任何 AI。用于测试：
- 可重复（同输入同输出）
- 零成本、零网络
- 能记录收到的 prompt，让测试断言 prompt 内容

两种用法：
  FakeLLM(canned_response="x")        —— 不管 prompt，永远返回 x
  FakeLLM(responder=lambda p: ...)    —— 按 prompt 规则决定回复
"""
from __future__ import annotations

from typing import Callable

from ports.llm_client import LLMClient


class FakeLLM(LLMClient):
    def __init__(self,
                 canned_response: str | None = None,
                 responder: Callable[[str], str] | None = None) -> None:
        if canned_response is None and responder is None:
            raise ValueError("必须提供 canned_response 或 responder 之一")
        self._canned = canned_response
        self._responder = responder
        self.received_prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.received_prompts.append(prompt)
        if self._responder is not None:
            return self._responder(prompt)
        return self._canned  # type: ignore[return-value]

    @property
    def call_count(self) -> int:
        return len(self.received_prompts)
