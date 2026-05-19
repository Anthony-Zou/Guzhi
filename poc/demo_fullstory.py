"""故知 · 完整故事演示 —— 从自述文本到相遇对话，走一遍 KG-First 全链路。

主角：孙听澜（SYN09）和 王南乔（SYN24）—— 30 人合成集里分数最高的一对，
他们共享两个 L3 存在性议题簇：去留之惑(S1) + 低谷停撑(S2)。

这个 demo 把 KG-First 的每一环都摊开打印，让你看清整条路：
  自述文本
    --[① 抽取]-->  KG 子图（一组带簇的边）
    --[② 匹配]-->  契合分 + 信号明细
    --[③ 种子]-->  故事种子（可叙事的素材）
    --[④ 推演]-->  相遇对话

注意：本 demo 全程用 FakeLLM / Stub —— 抽取和推演都不真调 Claude。
所以最后一步是占位文本，不是真对话。要看真对话，需要 ANTHROPIC_API_KEY
并把 StubKnowledgeExtractor / StubNarrator 换成 Claude 版（架构上一行不用改领域代码）。

用法：
    python3 demo_fullstory.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from domain.matching import match
from domain.seeds import extract_seeds
from adapters.stub_extractor import StubKnowledgeExtractor
from adapters.stub_narrator import StubNarrator
from adapters.in_memory_repository import InMemoryPersonaRepository
from app.matching_service import MatchingService
from synthetic.generator import TraitLibrary


LIB = TraitLibrary.default()

# ── 两位主角的"自述文本" ──────────────────────────────────────
# 这两段是为 demo 手写的，措辞里嵌入了 StubKnowledgeExtractor 认得的关键词
# （这样 stub 抽取器能抽出边）。真实产品里，用户怎么写都行，靠真 LLM 抽。
TEXT_SUN = """\
我今年三十，在北京。最近脑子里一直转着一件事：要不要回老家。
不是混不下去，是忽然觉得"留下"这件事得有个理由，我答不上来。
工作上也撑得很累，常想该不该停下来歇歇——可一停下来又怕自己就废了。
"""

TEXT_WANG = """\
我在上海待了五年，去年开始反复想：留下还是离开。
这座城市到底还值不值得待，我没有答案。
状态其实很差，但不敢停——需要一个喘息的理由，又找不到。
"""


def sep(title: str) -> None:
    print()
    print("━" * 60)
    print(f" {title}")
    print("━" * 60)


def show_edges(persona) -> None:
    """打印一个人物抽取出的 KG 子图。"""
    clustered = [e for e in persona.edges if e.cluster]
    noise = [e for e in persona.edges if not e.cluster]
    for e in clustered:
        cl = LIB.clusters[e.cluster]
        print(f"   [{e.relation:11s}] {e.entity}")
        print(f"      └─ 归簇 {e.cluster}「{cl.name}」({cl.level.value})  "
              f"强度 {e.strength}")
    for e in noise:
        print(f"   [{e.relation:11s}] {e.entity}  （噪音边，不进匹配）")
    if not persona.edges:
        print("   （没抽出任何边）")


def main() -> None:
    print()
    print("故知 · 完整故事演示")
    print("KG-First 全链路：自述文本 → 抽取 → 匹配 → 种子 → 推演")
    print("（本 demo 全程 FakeLLM / Stub，最后一步是占位文本）")

    extractor = StubKnowledgeExtractor(LIB)

    # ── ① 抽取：自述文本 → KG 子图 ──────────────────────────
    sep("① 抽取 —— 把自述文本变成知识图谱子图")
    print("\n【孙听澜 的自述】")
    print("   " + TEXT_SUN.strip().replace("\n", "\n   "))
    sun = extractor.extract(TEXT_SUN, "SUN", "孙听澜", "female")
    print("\n   ↓ 抽取出的 KG 边：")
    show_edges(sun)

    print("\n【王南乔 的自述】")
    print("   " + TEXT_WANG.strip().replace("\n", "\n   "))
    wang = extractor.extract(TEXT_WANG, "WANG", "王南乔", "male")
    print("\n   ↓ 抽取出的 KG 边：")
    show_edges(wang)

    print("\n   说明：抽取这一步在真实产品里由 Claude 完成。这里用规则式 stub，")
    print("   它只能认出预设关键词 —— 这正是为什么需要真 LLM。")

    # ── ② 匹配：两张子图 → 契合分 ──────────────────────────
    sep("② 匹配 —— 纯图运算，零 AI")
    result = match(sun, wang, LIB.clusters, LIB.tension_pairs,
                   LIB.style_complement_pairs)
    print(f"\n   孙听澜  ╳  王南乔")
    print(f"   匹配：{'是' if result.matched else '否'}    契合分：{result.score}")
    print(f"   共享语义簇：{list(result.shared_clusters)}")
    for cid in result.shared_clusters:
        cl = LIB.clusters[cid]
        print(f"      - {cid}「{cl.name}」({cl.level.value})")
    print("\n   信号明细（分数怎么来的 —— 这就是 KG-First 的可解释性）：")
    for name, val in result.signals.items():
        if val > 0:
            print(f"      {name}: {val}")
    print("\n   说明：匹配完全是确定性的图运算。AI 没有参与判断。")

    # ── ③ 故事种子：从匹配里挖可叙事的素材 ──────────────────
    sep("③ 故事种子 —— 从匹配里挖出可叙事的素材")
    seeds = extract_seeds(sun, wang, set(result.shared_clusters),
                          LIB.clusters, LIB.tension_pairs)
    for i, s in enumerate(seeds, 1):
        print(f"\n   种子 {i}：{s.seed_type}  来自簇「{LIB.clusters[s.cluster].name}」")
        print(f"      孙听澜 这边：{s.a_entity}")
        print(f"        └─ 原话：{s.a_evidence}")
        print(f"      王南乔 这边：{s.b_entity}")
        print(f"        └─ 原话：{s.b_evidence}")
        print(f"      故事感权重：{s.weight}")
    print("\n   说明：种子是 AI 推演的唯一输入。AI 不拿两个人的完整资料，")
    print("   只拿这一颗种子 —— 这是 KG-First 的核心：AI 只做最后一公里。")

    # ── ④ 推演：故事种子 → 相遇对话 ──────────────────────────
    sep("④ 推演 —— AI 拿种子写一段相遇对话")
    repo = InMemoryPersonaRepository(
        personas=[sun, wang],
        clusters=LIB.clusters,
        tension_pairs=LIB.tension_pairs,
        style_complement_pairs=LIB.style_complement_pairs,
    )
    service = MatchingService(repo, StubNarrator())
    story = service.narrate_match(result)
    print()
    for line in story.splitlines():
        print(f"   {line}")
    print("\n   说明：这一步用的是 StubNarrator —— 占位文本。")
    print("   把它换成 ClaudeNarrator（已写好，等 ANTHROPIC_API_KEY），")
    print("   这里就会是 Claude 基于上面那颗种子生成的 6-10 轮真实对话。")

    sep("链路走完")
    print("\n   自述文本 → 抽取 → 匹配 → 种子 → 推演")
    print("   全程：抽取(stub) + 匹配(纯图运算) + 推演(stub)")
    print("   两个真正用 AI 的点（抽取、推演）都已写好 Claude 版，")
    print("   只差一个 API key。领域逻辑一行都不用改 —— 这就是六边形架构。")
    print()


if __name__ == "__main__":
    main()
