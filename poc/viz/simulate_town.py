"""小镇模拟剧本生成器 —— 让 30 个 agent 在 2D 网格里游走 N 个 ticks。

每 tick 记录所有位置；agent 相遇时调 match() 实时算分，匹配上的对触发事件。
输出一个自包含的 JSON 剧本，给前端回放。

这是"会动的小镇"的后端。诚实地说：agent 是随机游走，不是 smart agent ——
没有真实奖励信号，做 smart agent 也是假 smart。重点是"看到一群人在镇上走、
相遇时算法实时跑、能看清这套机制怎么工作"。

复用：
  - 30 个合成人物（synthetic.generator）
  - match() 匹配引擎（domain.matching）
  - extract_seeds() 故事种子（domain.seeds）
  - StubNarrator 推演占位（adapters.stub_narrator）
"""
from __future__ import annotations

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.matching import match
from domain.seeds import extract_seeds
from adapters.stub_narrator import StubNarrator
from synthetic.generator import TraitLibrary, PersonaGenerator

# ─── 模拟参数 ────────────────────────────────────────────────
GRID_W = 40
GRID_H = 30
N_TICKS = 300
N_PERSONAS = 30
MEETING_RADIUS = 1          # 曼哈顿距离 <= 1 = 相遇
MEETING_COOLDOWN = 50       # 同一对人 50 ticks 内不重复
SEED = 42

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(HERE, "town_simulation.json")

# 社交动力学参数
PERCEPTION_RADIUS = 5     # agent 能"看到"周围多少格内的邻居
COOLDOWN_REPEL = 0.6      # 刚见过的人有多排斥
SOFTMAX_TEMP = 0.7        # 决策温度，低温更确定、高温更随机


def _manhattan(p, q):
    return abs(p[0] - q[0]) + abs(p[1] - q[1])


def _random_step(rng, pos, *_unused):
    """路线 A — 纯随机游走（基线）。"""
    dx, dy = rng.choice([(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)])
    nx, ny = pos[0] + dx, pos[1] + dy
    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
        return (nx, ny)
    return pos


def _venue_bonus(pos, venue_pref, center):
    """场所偏好梯度 —— 离自己喜欢的地方越近，得分越高。"""
    if venue_pref == "center":
        d = _manhattan(pos, center)
        return -d * 0.05   # 离中心越远，分越低
    if venue_pref == "edge":
        # 离最近的边
        d_edge = min(pos[0], pos[1], GRID_W-1-pos[0], GRID_H-1-pos[1])
        return -d_edge * 0.04
    return 0.0   # neutral


def _social_step(rng, pos, agent_id, all_positions, last_meeting,
                 extroversion, venue_pref, current_tick):
    """路线 C — 社交动力学游走。

    决策思路：每个候选方向（5 个，含原地）算一个"想去那的得分"，softmax 抽样。
    得分组成：
      - 周围邻居数 × extroversion：外向的爱聚，内向的爱散
      - 场所偏好梯度
      - 刚见过的邻居产生排斥
    """
    center = (GRID_W // 2, GRID_H // 2)
    moves = [(-1, 0), (1, 0), (0, -1), (0, 1), (0, 0)]

    scores = []
    for dx, dy in moves:
        nx, ny = pos[0] + dx, pos[1] + dy
        # 撞墙：给极低分但还在候选里（softmax 会几乎不选）
        if not (0 <= nx < GRID_W and 0 <= ny < GRID_H):
            scores.append(-10.0)
            continue
        # 这个候选位置的得分
        s = 0.0
        # 1. 邻居引力 / 排斥
        neighbor_score = 0.0
        for other_id, other_pos in all_positions.items():
            if other_id == agent_id:
                continue
            d = _manhattan((nx, ny), other_pos)
            if d > PERCEPTION_RADIUS:
                continue
            # 距离 1-5：越近影响越大
            proximity = (PERCEPTION_RADIUS + 1 - d) / PERCEPTION_RADIUS
            # 冷却中的邻居：施加排斥
            key = tuple(sorted([agent_id, other_id]))
            in_cooldown = (current_tick - last_meeting.get(key, -10**9)
                           < MEETING_COOLDOWN)
            if in_cooldown:
                neighbor_score -= proximity * COOLDOWN_REPEL
            else:
                # 外向(extroversion接近1) → 吸引；内向(接近0) → 排斥
                pull = (extroversion - 0.5) * 2   # 映射到 [-1, 1]
                neighbor_score += proximity * pull
        s += neighbor_score
        # 2. 场所偏好
        s += _venue_bonus((nx, ny), venue_pref, center)
        scores.append(s)

    # Softmax 抽样
    max_s = max(scores)
    exps = [pow(2.718281828, (s - max_s) / SOFTMAX_TEMP) for s in scores]
    total = sum(exps)
    probs = [e / total for e in exps]
    # 累积分布抽样
    r = rng.random()
    acc = 0.0
    chosen = 4  # default: 不动
    for i, p in enumerate(probs):
        acc += p
        if r < acc:
            chosen = i
            break
    dx, dy = moves[chosen]
    nx, ny = pos[0] + dx, pos[1] + dy
    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
        return (nx, ny)
    return pos


def _build_one_liner(persona, lib, deepest_level: str | None) -> str:
    """一句抵达性总结：拼接式但读起来像人话。

    规则：取这个人最深等级里最强的两个簇，套不同句式。
      - 都 L3 -> "在 X 里，也想着 Y"
      - 一 L3 一 L2 -> "在 X 里，信着 Y"
      - 都 L2 -> "信着 X，也信着 Y"
      - 都 L1 -> "爱 X，也爱 Y"
      - 只一个簇 -> 单子句
    """
    if not deepest_level:
        return "（特质不详）"
    # 把这人涉及的簇按"等级 + 在 KG 里的最高 strength"排
    rank = {"L3": 0, "L2": 1, "L1": 2}
    cluster_strength: dict[str, float] = {}
    for e in persona.edges:
        if e.cluster and e.cluster in lib.clusters:
            cluster_strength[e.cluster] = max(
                cluster_strength.get(e.cluster, 0), e.strength)
    ordered = sorted(
        cluster_strength.items(),
        key=lambda kv: (rank.get(lib.clusters[kv[0]].level.value, 9), -kv[1]),
    )
    if not ordered:
        return "（特质不详）"

    L = lib.cluster_label
    if len(ordered) == 1:
        cid = ordered[0][0]
        return f"在「{L[cid]}」里"

    cid_a, cid_b = ordered[0][0], ordered[1][0]
    lv_a = lib.clusters[cid_a].level.value
    lv_b = lib.clusters[cid_b].level.value
    a, b = L[cid_a], L[cid_b]

    # L 标签本身已经是人物画像短语（如"低谷里的人"、"反内卷者"）
    if lv_a == "L3" and lv_b == "L3":
        return f"既在「{a}」，也在「{b}」"
    if lv_a == "L3" and lv_b == "L2":
        return f"在「{a}」，相信「{b}」"
    if lv_a == "L2":
        return f"相信「{a}」，也相信「{b}」"
    # L1 + L1
    return f"是「{a}」，也是「{b}」"


def simulate(mode: str = "random") -> dict:
    """跑一次完整模拟，返回剧本 dict。

    mode: 'random' = 纯随机游走（基线）
          'social' = 社交动力学（外向度 + 场所偏好 + 冷却排斥）
    """
    if mode not in ("random", "social"):
        raise ValueError(f"mode must be 'random' or 'social', got {mode!r}")

    lib = TraitLibrary.default()
    gen = PersonaGenerator(lib, seed=SEED)
    personas = gen.generate(N_PERSONAS)
    by_id = {p.id: p for p in personas}
    narrator = StubNarrator()
    # 主流随机数：游走决策
    rng = random.Random(SEED + 1 + (100 if mode == "social" else 0))
    # 社交参数派生：独立 RNG，不污染特质流
    social_rng = random.Random(SEED + 200000)
    # 每个 agent 的社交属性
    social_attrs: dict[str, dict] = {}
    for p in personas:
        social_attrs[p.id] = {
            "extroversion": round(social_rng.random(), 2),  # [0,1]
            "venue_pref": social_rng.choice(["center", "edge", "neutral"]),
        }

    # 给每个 agent 一个初始位置（不重叠）
    occupied = set()
    positions: dict[str, tuple[int, int]] = {}
    for p in personas:
        while True:
            pos = (rng.randint(0, GRID_W - 1), rng.randint(0, GRID_H - 1))
            if pos not in occupied:
                occupied.add(pos)
                positions[p.id] = pos
                break

    # 相遇冷却：(id_a, id_b) 排序后 -> 最后一次相遇的 tick
    last_meeting: dict[tuple[str, str], int] = {}

    ticks_data: list[dict] = []
    events: list[dict] = []

    for tick in range(N_TICKS):
        # 移动每个 agent —— mode 决定用哪种策略
        # 注意：social 模式里所有人共享同一份 positions 快照（顺序更新会让先动的"看到"后动的旧位置；这是可接受的简化）
        snapshot_positions = dict(positions)
        for p in personas:
            if mode == "social":
                attrs = social_attrs[p.id]
                positions[p.id] = _social_step(
                    rng, positions[p.id], p.id,
                    snapshot_positions, last_meeting,
                    attrs["extroversion"], attrs["venue_pref"], tick,
                )
            else:
                positions[p.id] = _random_step(rng, positions[p.id])

        tick_positions = {pid: list(pos) for pid, pos in positions.items()}
        tick_events: list[dict] = []

        # 检测相遇（只算每对一次）
        ids = list(positions.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a_id, b_id = ids[i], ids[j]
                if _manhattan(positions[a_id], positions[b_id]) > MEETING_RADIUS:
                    continue
                # 冷却
                key = tuple(sorted([a_id, b_id]))
                if tick - last_meeting.get(key, -MEETING_COOLDOWN) < MEETING_COOLDOWN:
                    continue
                last_meeting[key] = tick

                # 跑匹配
                a, b = by_id[a_id], by_id[b_id]
                r = match(a, b, lib.clusters, lib.tension_pairs,
                          lib.style_complement_pairs)

                event = {
                    "tick": tick,
                    "a_id": a_id, "b_id": b_id,
                    "a_name": a.name, "b_name": b.name,
                    "a_name_en": gen.name_en_for(a_id),
                    "b_name_en": gen.name_en_for(b_id),
                    "a_pos": list(positions[a_id]),
                    "b_pos": list(positions[b_id]),
                    "matched": r.matched,
                    "score": r.score,
                    "shared_clusters": list(r.shared_clusters),
                }

                if r.matched:
                    seeds = extract_seeds(
                        a, b, set(r.shared_clusters),
                        lib.clusters, lib.tension_pairs)
                    if seeds:
                        top = seeds[0]
                        event["seed"] = {
                            "seed_type": top.seed_type,
                            "cluster": top.cluster,
                            "cluster_name": lib.clusters[top.cluster].name,
                            "cluster_name_en": lib.cluster_name_en.get(top.cluster, lib.clusters[top.cluster].name),
                            "a_entity": top.a_entity,
                            "b_entity": top.b_entity,
                            "weight": top.weight,
                        }
                        event["narration"] = narrator.narrate(top, a, b)
                tick_events.append(event)
                events.append(event)

        ticks_data.append({
            "tick": tick,
            "positions": tick_positions,
            "events": tick_events,
        })

    # 预先算"全量潜在匹配"：每个人 vs 库里所有人，按 score 排
    # 这是"她本该遇到谁"的事实依据，独立于这次模拟的随机游走。
    potential_matches_for: dict[str, list[dict]] = {p.id: [] for p in personas}
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            a, b = personas[i], personas[j]
            r = match(a, b, lib.clusters, lib.tension_pairs,
                      lib.style_complement_pairs)
            if not r.matched:
                continue
            entry_a = {
                "with_id": b.id, "with_name": b.name,
                "score": r.score, "shared": list(r.shared_clusters),
            }
            entry_b = {
                "with_id": a.id, "with_name": a.name,
                "score": r.score, "shared": list(r.shared_clusters),
            }
            potential_matches_for[a.id].append(entry_a)
            potential_matches_for[b.id].append(entry_b)
    # 各自按 score 降序
    for pid in potential_matches_for:
        potential_matches_for[pid].sort(key=lambda x: -x["score"])

    # 人物元信息（前端渲染要用）
    personas_meta = []
    for p in personas:
        # 颜色按最深簇等级
        levels = [lib.clusters[c].level.value for c in p.clusters_present()
                  if c in lib.clusters]
        deepest = ("L3" if "L3" in levels
                   else "L2" if "L2" in levels
                   else "L1" if "L1" in levels else None)
        # 这个人的几条核心 KG 边（带簇的边，按 strength 排前 4）
        core_edges = sorted(
            [e for e in p.edges if e.cluster],
            key=lambda e: -e.strength,
        )[:4]
        # 一句抵达性总结 —— 给前端 hover tooltip 用
        one_liner = _build_one_liner(p, lib, deepest)
        personas_meta.append({
            "id": p.id,
            "name": p.name,
            "name_en": gen.name_en_for(p.id),
            "gender": p.gender,
            "archetype": p.archetype,
            "one_liner": one_liner,
            "clusters": sorted(p.clusters_present()),
            "deepest_level": deepest,
            "core_edges": [
                {"relation": e.relation, "entity": e.entity,
                 "strength": e.strength, "cluster": e.cluster}
                for e in core_edges
            ],
            "potential_matches": potential_matches_for[p.id],
            # 社交属性（在 random 模式下显示但不起作用）
            "extroversion": social_attrs[p.id]["extroversion"],
            "venue_pref": social_attrs[p.id]["venue_pref"],
        })

    # 全局簇定义（前端要查 cluster_name / level / 簇的"是什么"描述）
    cluster_descriptions = {
        "S1": "在去与留之间反复的人 —— 一个城市值不值得待、要不要回家",
        "S2": "撑在低谷里的人 —— 累了想停下，又怕停下就废了",
        "S3": "身份在重组的人 —— 我不再是原来的我，还在找新的我",
        "S4": "在追问意义的人 —— 这些到底有没有意义、为谁活",
        "S5": "反效率主义的人 —— 不被 KPI 量化、慢下来不是错",
        "S6": "在意形式之美的人 —— 简洁、克制、boring 才是好工具",
        "S7": "独立自主的人 —— 不依附机构、自己定义成功",
        "S8": "诚实至上的人 —— 宁可难听也要真话",
        "S9": "反正能量表演的人 —— 受不了职场鸡汤、过度热情的客套",
        "S10": "文艺片影迷 —— 黑泽明、侯孝贤、蔡明亮那挂",
        "S11": "户外行动派 —— 徒步、长跑、攀岩",
        "S12": "古典乐迷 —— 巴赫、马勒、肖邦",
    }
    cluster_descriptions_en = {
        "S1": "Caught between staying and leaving — is this city worth it, should I go home",
        "S2": "Holding on through a trough — tired enough to stop, afraid that stopping ruins everything",
        "S3": "An identity being reassembled — I'm not who I was, and the new one isn't here yet",
        "S4": "Asking what for — does any of this mean anything, who am I living for",
        "S5": "Anti-grind — not to be quantified by KPIs, slowing down isn't a failure",
        "S6": "Devoted to form — clean, restrained, boring tools are the good ones",
        "S7": "On their own terms — not attached to any institution, defining success themselves",
        "S8": "Honesty above all — would rather be blunt than polite",
        "S9": "Allergic to performative positivity — corporate cheer, fake warmth",
        "S10": "Slow-cinema watcher — Kurosawa, Hou Hsiao-Hsien, Tsai Ming-liang",
        "S11": "Out where the wind is — hiking, long-distance running, climbing",
        "S12": "Classical listener — Bach, Mahler, Chopin",
    }
    clusters_meta = {
        cid: {
            "name": c.name,
            "name_en": lib.cluster_name_en.get(cid, c.name),
            "level": c.level.value,
            "description": cluster_descriptions.get(cid, ""),
            "description_en": cluster_descriptions_en.get(cid, ""),
        }
        for cid, c in lib.clusters.items()
    }

    return {
        "mode": mode,
        "grid": {"width": GRID_W, "height": GRID_H},
        "n_ticks": N_TICKS,
        "personas": personas_meta,
        "clusters": clusters_meta,
        "ticks": ticks_data,
        "events": events,
        "stats": {
            "n_personas": N_PERSONAS,
            "total_meetings": len(events),
            "matched_meetings": sum(1 for e in events if e["matched"]),
        },
    }


def main() -> None:
    # 跑两份：random（基线）+ social（路线 C）
    random_payload = simulate("random")
    social_payload = simulate("social")
    bundle = {
        "random": random_payload,
        "social": social_payload,
    }
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False)
    print(f"已生成 {OUTPUT_JSON}")
    for mode in ("random", "social"):
        s = bundle[mode]["stats"]
        print(f"  [{mode}] {N_TICKS} ticks · {s['n_personas']} 人 · "
              f"{s['total_meetings']} 次相遇 · "
              f"{s['matched_meetings']} 次匹配上")


if __name__ == "__main__":
    main()
