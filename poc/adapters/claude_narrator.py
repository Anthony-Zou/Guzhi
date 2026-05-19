"""adapter — ClaudeNarrator。

实现 Narrator 端口。组合两样东西：
  - domain.narration_prompt.build_narration_prompt  —— 构建 prompt（领域逻辑）
  - LLMClient                                       —— 真正调 LLM（注入）

测试时注入 FakeLLM，生产时注入 AnthropicLLM。
ClaudeNarrator 自己不碰 anthropic SDK，也不碰 prompt 的"设计" ——
它只负责"把领域逻辑和 IO 接起来"。这是 adapter 的本分。
"""
from __future__ import annotations

from domain.models import Persona
from domain.seeds import StorySeed
from domain.narration_prompt import build_narration_prompt
from ports.narrator import Narrator
from ports.llm_client import LLMClient


class ClaudeNarrator(Narrator):
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def narrate(self, seed: StorySeed, a: Persona, b: Persona,
                call_point: str | None = None,
                shared_clusters: tuple[str, ...] | None = None,
                scene_seed: int | None = None) -> str:
        """拿故事种子 + 两个人 -> 构建 prompt -> 调 LLM -> 返回对话文本。

        call_point/shared_clusters: 这个实现不路由也不 enrich,纯粹忽略。
                                   要那些请用 RoutedNarrator。
        scene_seed: 给定则场景确定（可重复）；不给则随机。
        """
        del call_point, shared_clusters
        prompt = build_narration_prompt(seed, a, b, scene_seed=scene_seed)
        return self._llm.complete(prompt)
