"""adapter — InMemoryPersonaRepository。

实现 PersonaRepository 端口，数据存在内存里，支持运行时新增人物。

为什么需要它：
JsonPersonaRepository 是只读的（从文件加载一次）。但"从文本注册新人物"
这个链路需要一个能写的 repo —— 抽取出 Persona 后要放得进去。
内存 repo 最简单，适合 POC 和测试。

未来规模化时，换成 SQLite / Postgres 的 repo，同样实现这个端口即可。
"""
from __future__ import annotations

from domain.models import Persona, Cluster
from ports.persona_repository import PersonaRepository


class InMemoryPersonaRepository(PersonaRepository):
    def __init__(self,
                 personas: list[Persona],
                 clusters: dict[str, Cluster],
                 tension_pairs: list[tuple[str, str, str]],
                 style_complement_pairs: list[tuple[str, str]]) -> None:
        self._personas: dict[str, Persona] = {p.id: p for p in personas}
        self._clusters = dict(clusters)
        self._tension_pairs = list(tension_pairs)
        self._style_complement_pairs = list(style_complement_pairs)

    # ---- 读 ----
    def all_personas(self) -> list[Persona]:
        return list(self._personas.values())

    def get(self, persona_id: str) -> Persona:
        if persona_id not in self._personas:
            raise KeyError(f"未找到人物: {persona_id}")
        return self._personas[persona_id]

    def clusters(self) -> dict[str, Cluster]:
        return dict(self._clusters)

    def tension_pairs(self) -> list[tuple[str, str, str]]:
        return list(self._tension_pairs)

    def style_complement_pairs(self) -> list[tuple[str, str]]:
        return list(self._style_complement_pairs)

    # ---- 写 ----（端口之外的扩展能力，内存 repo 特有）
    def add(self, persona: Persona) -> None:
        """新增（或覆盖）一个人物。"""
        self._personas[persona.id] = persona
