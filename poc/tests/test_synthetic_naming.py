"""TDD — 合成人物的真人名 + 性别 + 画像。

演进历程：
  v1: SYN01 代号 —— 看不懂
  v2: "去留之间·01" 语义标签 —— 大量重复，而且这是"标签"不是"人名"
  v3（现在）: 真人名（陈晓雨）+ 性别 + archetype 画像

设计：
  - id     = SYN01     机器用，稳定
  - name   = 真人名    人看，男女各半，名字与性别匹配
  - gender = male/female
  - archetype = "去留之间·低谷里的人"  这个人的特质画像（之前冒充 name 的东西）
  - gender 不进入匹配算法 —— 纯 KG 匹配，性别只是展示信息
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.models import ClusterLevel
from synthetic.generator import TraitLibrary, PersonaGenerator


def test_every_cluster_has_a_persona_label():
    """特质库里每个簇都要有一个'画像标签'，供 archetype 用。"""
    lib = TraitLibrary.default()
    for cid in lib.clusters:
        assert cid in lib.cluster_label, f"簇 {cid} 没有画像标签"
        assert len(lib.cluster_label[cid]) >= 2


def test_persona_id_still_machine_readable():
    """id 仍是 SYN01 这种 —— 机器用、稳定、可排序。"""
    g = PersonaGenerator(TraitLibrary.default(), seed=42)
    personas = g.generate(count=5)
    assert personas[0].id == "SYN01"
    assert personas[4].id == "SYN05"


def test_persona_name_is_a_real_human_name():
    """name 是真人名 —— 不是代号、不是语义标签、不含分隔符。"""
    g = PersonaGenerator(TraitLibrary.default(), seed=42)
    personas = g.generate(count=30)
    for p in personas:
        assert p.name != p.id, f"{p.id} 的 name 还是代号"
        # 真人名不该含 · 分隔符（那是旧的语义标签格式）
        assert "·" not in p.name, f"{p.id} 的 name 还是语义标签: {p.name}"
        # 中文名长度合理（2-4 字）
        assert 2 <= len(p.name) <= 4, f"{p.id} 名字长度可疑: {p.name}"


def test_persona_has_gender():
    """每个人物有 gender 字段，取值 male / female。"""
    g = PersonaGenerator(TraitLibrary.default(), seed=42)
    personas = g.generate(count=30)
    for p in personas:
        assert p.gender in ("male", "female"), (
            f"{p.id} 的 gender 非法: {p.gender}"
        )


def test_gender_roughly_balanced():
    """30 个人物男女大致各半（允许偏差）。"""
    g = PersonaGenerator(TraitLibrary.default(), seed=42)
    personas = g.generate(count=30)
    males = sum(1 for p in personas if p.gender == "male")
    # 30 人，男性应在 10-20 之间（不要求精确各半，但不能极端失衡）
    assert 10 <= males <= 20, f"性别失衡: {males} 男 / {30 - males} 女"


def test_persona_has_archetype():
    """archetype 字段保留'特质画像' —— 之前冒充 name 的两簇标签。"""
    lib = TraitLibrary.default()
    g = PersonaGenerator(lib, seed=42)
    personas = g.generate(count=30)
    for p in personas:
        assert p.archetype, f"{p.id} 没有 archetype"
        # archetype 首段应是最深簇的标签
        clusters_present = p.clusters_present()
        levels = {lib.clusters[c].level for c in clusters_present}
        if ClusterLevel.L3 in levels:
            deepest = ClusterLevel.L3
        elif ClusterLevel.L2 in levels:
            deepest = ClusterLevel.L2
        else:
            deepest = ClusterLevel.L1
        deepest_labels = {
            lib.cluster_label[c] for c in clusters_present
            if lib.clusters[c].level == deepest
        }
        first_label = p.archetype.split("·")[0]
        assert first_label in deepest_labels, (
            f"{p.id} archetype '{p.archetype}' 首段不在最深簇标签里"
        )


def test_names_can_repeat_but_ids_unique():
    """真人名可以重名（现实里也会），但 id 必须唯一。

    重名靠 id 区分 —— 这才是真实世界的样子。
    """
    g = PersonaGenerator(TraitLibrary.default(), seed=42)
    personas = g.generate(count=30)
    ids = [p.id for p in personas]
    assert len(ids) == len(set(ids)), "id 必须唯一"


def test_generation_is_deterministic():
    """同 seed 两次生成，名字/性别/画像必须完全一致。"""
    g1 = PersonaGenerator(TraitLibrary.default(), seed=7)
    g2 = PersonaGenerator(TraitLibrary.default(), seed=7)
    p1 = g1.generate(count=30)
    p2 = g2.generate(count=30)
    assert [(p.name, p.gender, p.archetype) for p in p1] == \
           [(p.name, p.gender, p.archetype) for p in p2]
