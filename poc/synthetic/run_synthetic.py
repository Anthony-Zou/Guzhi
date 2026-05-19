"""在 30 个合成人物上跑匹配算法，对照机械真值表，输出诊断。

这是验证的核心脚本。它回答：现有算法能不能复现生成器的'设计意图'？
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.matching import match
from synthetic.generator import (
    TraitLibrary, PersonaGenerator, ground_truth_for,
)

SEED = 42
COUNT = 30
DATA_OUT = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")


def main() -> None:
    lib = TraitLibrary.default()
    gen = PersonaGenerator(lib, seed=SEED)
    personas = gen.generate(COUNT)
    truth = ground_truth_for(personas, lib)

    # 落盘：人物 + 真值表
    os.makedirs(os.path.join(DATA_OUT, "personas"), exist_ok=True)
    for p in personas:
        with open(os.path.join(DATA_OUT, "personas", f"{p.id}.json"),
                  "w", encoding="utf-8") as f:
            json.dump({
                "id": p.id, "name": p.name,
                "gender": p.gender, "archetype": p.archetype,
                "edges": [
                    {"relation": e.relation, "entity": e.entity,
                     "strength": e.strength, "cluster": e.cluster,
                     "evidence": e.evidence}
                    for e in p.edges
                ],
            }, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_OUT, "ground_truth.json"),
              "w", encoding="utf-8") as f:
        json.dump({k: sorted(v) for k, v in truth.items()},
                  f, ensure_ascii=False, indent=2)

    clusters = lib.clusters
    tension = lib.tension_pairs
    style_comp = lib.style_complement_pairs

    # 跑所有对
    by_id = {p.id: p for p in personas}
    algo_matched: dict[str, set[str]] = {p.id: set() for p in personas}
    all_pairs = []
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            a, b = personas[i], personas[j]
            r = match(a, b, clusters, tension, style_comp)
            all_pairs.append(r)
            if r.matched:
                algo_matched[a.id].add(b.id)
                algo_matched[b.id].add(a.id)

    # 混淆矩阵（pair 级）
    tp = fp = fn = tn = 0
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            a, b = personas[i].id, personas[j].id
            should = b in truth[a]
            did = b in algo_matched[a]
            if should and did:
                tp += 1
            elif should and not did:
                fn += 1
            elif not should and did:
                fp += 1
            else:
                tn += 1

    total_pairs = tp + fp + fn + tn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    accuracy = (tp + tn) / total_pairs

    print("=" * 60)
    print(f"合成数据验证 — {COUNT} 人, {total_pairs} 对, seed={SEED}")
    print("=" * 60)
    print(f"真值表里'该匹配'的对数: {tp + fn}")
    print(f"算法判'匹配'的对数:     {tp + fp}")
    print()
    print("混淆矩阵（pair 级）:")
    print(f"  TP 该配且配上  = {tp}")
    print(f"  FN 该配没配上  = {fn}   <- 算法漏掉的")
    print(f"  FP 不该配却配上 = {fp}   <- 算法误配的")
    print(f"  TN 不该配也没配 = {tn}")
    print()
    print(f"  Precision 精确率 = {precision:.1%}")
    print(f"  Recall    召回率 = {recall:.1%}")
    print(f"  F1               = {f1:.1%}")
    print(f"  Accuracy  准确率 = {accuracy:.1%}")
    print()

    # FN 诊断：算法为什么漏
    print("--- FN 样本诊断（算法漏掉的，最多 10 个）---")
    shown = 0
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            if shown >= 10:
                break
            a, b = personas[i], personas[j]
            should = b.id in truth[a.id]
            did = b.id in algo_matched[a.id]
            if should and not did:
                r = match(a, b, clusters, tension, style_comp)
                shared = a.clusters_present() & b.clusters_present()
                shared_lv = {cid: clusters[cid].level.value for cid in shared}
                print(f"  {a.id}-{b.id}: score={r.score:.3f} "
                      f"reason={r.reason} shared={shared_lv}")
                shown += 1

    # FP 诊断：算法为什么误配
    print()
    print("--- FP 样本诊断（算法误配的，最多 10 个）---")
    shown = 0
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            if shown >= 10:
                break
            a, b = personas[i], personas[j]
            should = b.id in truth[a.id]
            did = b.id in algo_matched[a.id]
            if not should and did:
                r = match(a, b, clusters, tension, style_comp)
                shared = a.clusters_present() & b.clusters_present()
                shared_lv = {cid: clusters[cid].level.value for cid in shared}
                print(f"  {a.id}-{b.id}: score={r.score:.3f} "
                      f"shared={shared_lv}")
                shown += 1

    print()
    print(f"数据已落盘: {DATA_OUT}")


if __name__ == "__main__":
    main()
