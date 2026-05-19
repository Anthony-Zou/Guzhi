"""端到端验收测试 — 30 人合成数据集上的算法表现。

这是 POC 真正的验收标准。8 人数据集太小、真值表偏乐观，不可靠；
30 人合成数据集的真值表是生成器机械规则的产物（不是主观判断），
且生成规则与匹配算法逻辑不同（防循环论证）。

若算法能在 30 人上复现生成器的设计意图，才说明 KG-First 架构成立。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.matching import match
from synthetic.generator import (
    TraitLibrary, PersonaGenerator, ground_truth_for,
)

SEED = 42
COUNT = 30


def _run():
    """跑 30 人 435 对，返回混淆矩阵。"""
    lib = TraitLibrary.default()
    personas = PersonaGenerator(lib, seed=SEED).generate(COUNT)
    truth = ground_truth_for(personas, lib)

    algo_matched = {p.id: set() for p in personas}
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            a, b = personas[i], personas[j]
            r = match(a, b, lib.clusters, lib.tension_pairs,
                      lib.style_complement_pairs)
            if r.matched:
                algo_matched[a.id].add(b.id)
                algo_matched[b.id].add(a.id)

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
    return tp, fp, fn, tn


def test_synthetic_recall_is_high():
    """召回率 >= 90% —— 生成器说该匹配的，算法不能大量漏掉。"""
    tp, fp, fn, tn = _run()
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    assert recall >= 0.90, f"召回率 {recall:.1%} 低于 90%"


def test_synthetic_precision_is_high():
    """精确率 >= 90% —— 算法说匹配的，不能大量误配。"""
    tp, fp, fn, tn = _run()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    assert precision >= 0.90, f"精确率 {precision:.1%} 低于 90%"


def test_synthetic_f1_is_high():
    """F1 >= 90% —— 综合指标。这是 POC 的核心验收标准。"""
    tp, fp, fn, tn = _run()
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    assert f1 >= 0.90, f"F1 {f1:.1%} 低于 90%"


def test_synthetic_deterministic():
    """同 seed 跑两次，混淆矩阵必须完全一致 —— 验证可复现。"""
    assert _run() == _run()
