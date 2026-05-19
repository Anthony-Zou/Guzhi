"""TDD — adapter 层：JsonPersonaRepository 测试。

adapter 实现 port 的抽象。这个 adapter 从 data/ 目录的 JSON 文件读人格。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from adapters.json_persona_repository import JsonPersonaRepository
from ports.persona_repository import PersonaRepository
from domain.models import Persona, Cluster

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def test_repository_implements_port():
    repo = JsonPersonaRepository(DATA_DIR)
    assert isinstance(repo, PersonaRepository)


def test_loads_all_eight_personas():
    repo = JsonPersonaRepository(DATA_DIR)
    personas = repo.all_personas()
    assert len(personas) == 8
    ids = {p.id for p in personas}
    assert ids == {"P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"}


def test_get_by_id():
    repo = JsonPersonaRepository(DATA_DIR)
    p1 = repo.get("P1")
    assert isinstance(p1, Persona)
    assert p1.name == "林知"
    # P1 应该有 12 条边
    assert len(p1.edges) == 12


def test_get_missing_raises():
    repo = JsonPersonaRepository(DATA_DIR)
    try:
        repo.get("P99")
        assert False, "找不到的 id 应该抛 KeyError"
    except KeyError:
        pass


def test_loads_clusters():
    repo = JsonPersonaRepository(DATA_DIR)
    clusters = repo.clusters()
    assert len(clusters) == 8
    assert "C1" in clusters
    c1 = clusters["C1"]
    assert isinstance(c1, Cluster)
    assert c1.name == "去留之惑"
    assert c1.level.value == "L3"


def test_loads_tension_pairs():
    repo = JsonPersonaRepository(DATA_DIR)
    pairs = repo.tension_pairs()
    assert len(pairs) >= 1
    # C7 簇内 野心会反噬人 vs 乱是关于宽恕
    assert any(cid == "C7" for cid, _, _ in pairs)


def test_loads_style_complement_pairs():
    repo = JsonPersonaRepository(DATA_DIR)
    pairs = repo.style_complement_pairs()
    assert ("锐利批判", "温柔细腻") in pairs or ("温柔细腻", "锐利批判") in pairs


def test_edges_carry_cluster_assignment():
    """P1 的'黑泽明'边应该被标到 C7 簇。"""
    repo = JsonPersonaRepository(DATA_DIR)
    p1 = repo.get("P1")
    heizeming = [e for e in p1.edges if e.entity == "黑泽明"][0]
    assert heizeming.cluster == "C7"
    assert heizeming.relation == "LIKES"
