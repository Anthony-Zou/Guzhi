"""故知 KG-First 匹配引擎 — POC 入口。

跑完整流程：加载人格 -> 匹配 -> 提取故事种子 -> AI 推演（stub）
-> 生成可视化 -> 在浏览器打开。
展示两个数据集的结果：8 人手工标注集、30 人合成集。

用法：
    python3 guzhi_poc.py            # 跑完整流程并自动打开可视化
    python3 guzhi_poc.py --no-open  # 只跑，不打开浏览器
"""
from __future__ import annotations

import os
import sys
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.json_persona_repository import JsonPersonaRepository
from adapters.stub_narrator import StubNarrator
from app.matching_service import MatchingService
from domain.matching import match
from synthetic.generator import (
    TraitLibrary, PersonaGenerator, ground_truth_for,
)
from viz.build_viz import build_payload, render_html, OUTPUT as VIZ_OUTPUT
from viz.build_town import render_town, OUTPUT as TOWN_OUTPUT

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _section(title: str) -> None:
    print()
    print("=" * 64)
    print(f" {title}")
    print("=" * 64)


def show_8_person_dataset() -> None:
    """8 人手工标注数据集 —— 演示 + 推演链路。"""
    _section("数据集 A：8 个手工标注人物")

    repo = JsonPersonaRepository(DATA_DIR)
    svc = MatchingService(repo, StubNarrator())

    print("\n每个人的匹配候选（按分数降序）：\n")
    for p in sorted(repo.all_personas(), key=lambda x: x.id):
        matches = svc.find_matches_for(p.id)
        if not matches:
            print(f"  {p.id} {p.name}：无匹配")
            continue
        tops = "  ".join(
            f"{m.persona_b}({m.score:.2f})" for m in matches[:3]
        )
        print(f"  {p.id} {p.name}：{tops}")

    report = svc.evaluate_against_truth()
    print(f"\n  对照真值表命中率：{report.hit_rate:.0%} "
          f"({report.hits}/{report.total})")
    print(f"  P7 被正确隔离：{report.p7_correct}")
    print("  注：8 人样本小、真值表偏乐观，命中率不作为硬指标。")

    # 演示推演链路
    print("\n  --- 故事推演演示（P1 的最佳匹配）---")
    p1_matches = svc.find_matches_for("P1")
    if p1_matches:
        story = svc.narrate_match(p1_matches[0])
        for line in story.splitlines():
            print(f"  {line}")


def show_30_person_dataset() -> None:
    """30 人合成数据集 —— 真正的验收。"""
    _section("数据集 B：30 个合成人物（机械真值表）")

    lib = TraitLibrary.default()
    personas = PersonaGenerator(lib, seed=42).generate(30)
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

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    print(f"\n  435 对，真值表'该匹配' {tp + fn} 对\n")
    print(f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}")
    print(f"  Precision = {precision:.1%}")
    print(f"  Recall    = {recall:.1%}")
    print(f"  F1        = {f1:.1%}")
    print("\n  这是 POC 的真实验收：算法能复现生成器的'设计意图'。")


def build_and_open_viz(auto_open: bool = True) -> None:
    """第三步：生成可视化 HTML，并在浏览器打开。"""
    _section("可视化 A：30 人匹配网络（力导向图）")
    payload = build_payload()
    path = render_html(payload)
    print(f"\n  已生成 {path}")
    if auto_open:
        url = "file://" + os.path.abspath(path)
        webbrowser.open(url)
        print(f"  已在浏览器打开 → {url}")
    else:
        print(f"  （--no-open：未自动打开。手动打开：{path}）")


def build_and_open_town(auto_open: bool = True) -> None:
    """第四步：生成小镇回放可视化，并在浏览器打开。"""
    _section("可视化 B：故知小镇 · 回放（像素小人 + 时间轴）")
    print("  跑 300 ticks 小镇模拟...")
    path = render_town()
    print(f"  已生成 {path}")
    if auto_open:
        url = "file://" + os.path.abspath(path)
        webbrowser.open(url)
        print(f"  已在浏览器打开 → {url}")
    else:
        print(f"  （--no-open：未自动打开。手动打开：{path}）")


def main() -> None:
    auto_open = "--no-open" not in sys.argv
    print("\n故知 · KG-First 匹配引擎 POC")
    print("架构：strict hexagonal | 开发：TDD")
    show_8_person_dataset()
    show_30_person_dataset()
    build_and_open_viz(auto_open=auto_open)
    build_and_open_town(auto_open=auto_open)
    print()


if __name__ == "__main__":
    main()
