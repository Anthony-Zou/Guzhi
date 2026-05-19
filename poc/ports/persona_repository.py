"""端口 — PersonaRepository。

六边形架构的"端口"：领域层对外的抽象接口。
领域/应用层只依赖这个抽象，不知道数据到底是从 JSON、SQLite 还是网络来的。
具体实现见 adapters/。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import Persona, Cluster


class PersonaRepository(ABC):
    """人格数据的来源。'从哪拿数据' 的抽象。"""

    @abstractmethod
    def all_personas(self) -> list[Persona]:
        """返回全部人格。"""
        ...

    @abstractmethod
    def get(self, persona_id: str) -> Persona:
        """按 id 取一个人格。找不到抛 KeyError。"""
        ...

    @abstractmethod
    def clusters(self) -> dict[str, Cluster]:
        """返回语义簇定义表。"""
        ...

    @abstractmethod
    def tension_pairs(self) -> list[tuple[str, str, str]]:
        """返回对立边对：[(cluster_id, entity_a, entity_b), ...]。"""
        ...

    @abstractmethod
    def style_complement_pairs(self) -> list[tuple[str, str]]:
        """返回互补风格对：[(style_a, style_b), ...]。"""
        ...
