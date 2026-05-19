"""把小镇模拟数据 + HTML 模板拼成自包含的 guzhi_town.html。

和 build_viz.py 完全对称。双击 guzhi_town.html 就能在浏览器看回放。
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from viz.simulate_town import simulate

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "town_template.html")
OUTPUT = os.path.join(HERE, "guzhi_town.html")


def render_town(bundle: dict | None = None) -> str:
    """生成自包含的 town HTML（含 random + social 两份模拟）。"""
    if bundle is None:
        bundle = {
            "random": simulate("random"),
            "social": simulate("social"),
        }
    with open(TEMPLATE, encoding="utf-8") as f:
        template = f.read()
    html = template.replace(
        "/*__PAYLOAD__*/",
        json.dumps(bundle, ensure_ascii=False),
    )
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)
    return OUTPUT


def main() -> None:
    bundle = {
        "random": simulate("random"),
        "social": simulate("social"),
    }
    path = render_town(bundle)
    print(f"已生成 {path}")
    for mode in ("random", "social"):
        s = bundle[mode]["stats"]
        print(f"  [{mode}] {s['total_meetings']} 相遇 · "
              f"{s['matched_meetings']} 匹配")


if __name__ == "__main__":
    main()
