"""端口 —— VenueSuggester。

匹配成功后,基于两人共同偏好生成一段短场地建议文本。

故知 P1.6 决定:不接 O2O 商家系统,不抽成。这一阶段只生成文本。
所以这个端口的实现可以是 Stub (确定性文本) / Claude / Routed。

注意区分:
- Narrator   → 写"两人相遇时聊的对话"
- VenueSuggester → 写"他们可以去什么类型的场地"
两件事 prompt 不同、输出格式不同,所以是独立端口。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import Persona


class VenueSuggester(ABC):
    @abstractmethod
    def suggest(self, a: Persona, b: Persona,
                call_point: str | None = None) -> str:
        """输入两个匹配上的人,输出一段短场地建议文本 (2-3 句)。

        call_point: 可选,RoutedVenueSuggester 用它决定走哪一档 (默认 Haiku)。
                    非路由实现忽略它。
        """
        ...
