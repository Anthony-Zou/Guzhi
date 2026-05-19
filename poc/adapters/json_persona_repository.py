"""adapter — JsonPersonaRepository。

实现 PersonaRepository 端口。从 data/ 目录的 JSON 文件读人格、簇、对立表。
这是"驱动侧"适配器：把外部数据格式翻译成领域对象。

适配器可以依赖 domain 和 ports，但 domain/ports 永远不依赖适配器。
"""
from __future__ import annotations

import glob
import json
import os

from domain.models import Edge, Persona, Cluster, ClusterLevel
from ports.persona_repository import PersonaRepository


class JsonPersonaRepository(PersonaRepository):
    def __init__(self, data_dir: str) -> None:
        self._data_dir = data_dir
        self._personas: dict[str, Persona] = {}
        self._clusters: dict[str, Cluster] = {}
        self._tension_pairs: list[tuple[str, str, str]] = []
        self._style_complement: list[tuple[str, str]] = []
        self._load()

    # ---- 加载 ----
    def _load(self) -> None:
        self._load_personas()
        self._load_clusters_file()

    def _load_personas(self) -> None:
        pattern = os.path.join(self._data_dir, "personas", "*.json")
        for path in sorted(glob.glob(pattern)):
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            edges = tuple(
                Edge(
                    relation=e["relation"],
                    entity=e["entity"],
                    strength=float(e["strength"]),
                    cluster=e.get("cluster"),
                    evidence=e.get("evidence", ""),
                )
                for e in raw["edges"]
            )
            persona = Persona(id=raw["id"], name=raw["name"], edges=edges)
            self._personas[persona.id] = persona

    def _load_clusters_file(self) -> None:
        path = os.path.join(self._data_dir, "clusters.json")
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        for cid, c in raw["clusters"].items():
            self._clusters[cid] = Cluster(
                id=cid,
                name=c["name"],
                level=ClusterLevel(c["level"]),
                signal=c["signal"],
            )

        for tp in raw.get("tension_pairs", []):
            self._tension_pairs.append(
                (tp["cluster"], tp["entity_a"], tp["entity_b"])
            )

        for pair in raw.get("style_complement_pairs", []):
            self._style_complement.append((pair[0], pair[1]))

    # ---- 端口实现 ----
    def all_personas(self) -> list[Persona]:
        return list(self._personas.values())

    def get(self, persona_id: str) -> Persona:
        if persona_id not in self._personas:
            raise KeyError(f"未找到人格: {persona_id}")
        return self._personas[persona_id]

    def clusters(self) -> dict[str, Cluster]:
        return dict(self._clusters)

    def tension_pairs(self) -> list[tuple[str, str, str]]:
        return list(self._tension_pairs)

    def style_complement_pairs(self) -> list[tuple[str, str]]:
        return list(self._style_complement)
