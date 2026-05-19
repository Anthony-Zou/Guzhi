"""把 30 人合成数据 + 匹配结果导出成一个自包含的单页 HTML。

复用 POC 的匹配引擎。产出 viz/guzhi_viz.html，双击即可在浏览器打开，
不需要服务器（数据直接内联进 HTML）。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.matching import match
from domain.seeds import extract_seeds
from synthetic.generator import (
    TraitLibrary, PersonaGenerator, ground_truth_for,
)

SEED = 42
COUNT = 30
HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "template.html")
OUTPUT = os.path.join(HERE, "guzhi_viz.html")


def build_payload() -> dict:
    lib = TraitLibrary.default()
    personas = PersonaGenerator(lib, seed=SEED).generate(COUNT)
    truth = ground_truth_for(personas, lib)

    # 簇定义
    clusters_json = {
        cid: {"name": c.name, "level": c.level.value, "signal": c.signal}
        for cid, c in lib.clusters.items()
    }

    # 人物（含边）
    personas_json = []
    for p in personas:
        personas_json.append({
            "id": p.id,
            "name": p.name,
            "gender": p.gender,
            "archetype": p.archetype,
            "clusters": sorted(p.clusters_present()),
            "edges": [
                {"relation": e.relation, "entity": e.entity,
                 "strength": e.strength, "cluster": e.cluster}
                for e in p.edges
            ],
        })

    # 所有匹配上的边（含分数、共簇、故事种子）
    by_id = {p.id: p for p in personas}
    links = []
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            a, b = personas[i], personas[j]
            r = match(a, b, lib.clusters, lib.tension_pairs,
                      lib.style_complement_pairs)
            if not r.matched:
                continue
            seeds = extract_seeds(a, b, set(r.shared_clusters),
                                  lib.clusters, lib.tension_pairs)
            top_seed = None
            if seeds:
                s = seeds[0]
                top_seed = {
                    "seed_type": s.seed_type,
                    "cluster": s.cluster,
                    "a_entity": s.a_entity,
                    "b_entity": s.b_entity,
                    "weight": s.weight,
                }
            # 与真值表对照
            should = b.id in truth[a.id]
            links.append({
                "source": a.id,
                "target": b.id,
                "score": r.score,
                "shared_clusters": list(r.shared_clusters),
                "signals": r.signals,
                "seed": top_seed,
                "in_truth": should,        # 算法配上了，真值表也说该配 -> True (TP)
            })

    # 真值表里"该配但算法没配"的 —— FN，也要显示出来
    matched_pairs = {(l["source"], l["target"]) for l in links}
    matched_pairs |= {(l["target"], l["source"]) for l in links}
    missed = []
    seen = set()
    for pid, partners in truth.items():
        for partner in partners:
            key = tuple(sorted([pid, partner]))
            if key in seen:
                continue
            seen.add(key)
            if (pid, partner) not in matched_pairs:
                missed.append({"source": key[0], "target": key[1]})

    # 统计
    tp = sum(1 for l in links if l["in_truth"])
    fp = sum(1 for l in links if not l["in_truth"])
    fn = len(missed)
    total_truth = tp + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / total_truth if total_truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    return {
        "clusters": clusters_json,
        "personas": personas_json,
        "links": links,
        "missed": missed,
        "stats": {
            "count": COUNT,
            "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        },
    }


def render_html(payload: dict | None = None) -> str:
    """把 payload 渲染进模板，写出 HTML 文件，返回文件路径。

    可被 guzhi_poc.py 直接调用，串成一条流程。
    """
    if payload is None:
        payload = build_payload()
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    html = template.replace(
        "/*__PAYLOAD__*/",
        json.dumps(payload, ensure_ascii=False),
    )
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    return OUTPUT


def main() -> None:
    payload = build_payload()
    path = render_html(payload)
    s = payload["stats"]
    print(f"已生成 {path}")
    print(f"  {s['count']} 人 | TP={s['tp']} FP={s['fp']} FN={s['fn']} "
          f"| F1={s['f1']:.1%}")


if __name__ == "__main__":
    main()
