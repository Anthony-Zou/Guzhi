"""端口 — Narrator。

'谁来做最后一步 AI 推演' 的抽象。
KG-First 原则：AI 只在这一个端口背后。换掉这个 adapter（真 Claude / stub / 别的模型），
领域逻辑完全不受影响。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import Persona
from domain.seeds import StorySeed


class Narrator(ABC):
    """故事推演器。拿一颗故事种子，写出一段两人相遇的对话。"""

    @abstractmethod
    def narrate(self, seed: StorySeed, a: Persona, b: Persona,
                call_point: str | None = None,
                shared_clusters: tuple[str, ...] | None = None) -> str:
        """输入一颗故事种子 + 两个人，输出一段对话文本。

        call_point: 可选的"调用点"标签 (来自 domain.routing.CallPoint)。
                    路由型 narrator (RoutedNarrator) 用它决定走哪一档模型;
                    非路由 narrator (ClaudeNarrator/StubNarrator) 忽略它。
                    向后兼容。
        shared_clusters: 可选的"两人共簇 id 元组"。RoutedNarrator 用它在
                    高档调用时做 enrich (从共簇里挑补充边塞 prompt)。
                    非路由 narrator 忽略它。低档调用也忽略 (Haiku 保持精简)。
        """
        ...
