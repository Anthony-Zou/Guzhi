"""端口 — KnowledgeExtractor。

抽象"一段自述文本 -> 一个 Persona（带 KG 边）"。

这是规模化的必经之路：真实产品不可能手工标注每个人的 KG 子图。
用户写一段自述，系统自动抽出边。

KG-First 架构里，AI 在两处出现，这是第二处（第一处是 Narrator 推演）。
和 Narrator 一样，AI 被关在端口背后 —— 换 stub / 真 LLM，
领域和应用层都不受影响。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import Persona


class KnowledgeExtractor(ABC):
    """从自述文本抽取知识图谱子图。"""

    @abstractmethod
    def extract(self, text: str, persona_id: str,
                name: str, gender: str = "",
                call_point: str | None = None) -> Persona:
        """输入一段自述文本 + 身份信息，输出一个带 KG 边的 Persona。

        text:       用户的自述文本
        persona_id: 机器用 id
        name:       展示用名字
        gender:     展示用性别（不参与匹配）
        call_point: 可选,路由型 extractor (RoutedExtractor) 用它决定走哪一档。
                    非路由 extractor 忽略它。向后兼容。
        """
        ...
