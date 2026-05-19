"""domain 层 — 推演 prompt 构建。

纯函数，零外部依赖。把"故事种子 + 两个人"转成一个交给 LLM 的 prompt。

为什么 prompt 构建放 domain 层：
prompt 的"设计"是领域知识 —— 哪些红线、哪些场景、对立种子和共鸣种子
该给什么指令 —— 这些是「故知」这个领域的规则，不是 IO 细节。
真正碰 IO 的（调 LLM）在 adapters/claude_narrator.py。

设计依据：设计文档第 7 节"AI 推演接口"。
"""
from __future__ import annotations

import random
from typing import Sequence

from domain.models import Persona
from domain.seeds import StorySeed
from domain.supporting_edges import SupportingEdge


# 场景池 —— 两人"相遇"的地点。给画面感，避免每次都一样。
SCENE_POOL = [
    "旧书店深处，午后",
    "便利店门口，深夜",
    "城市公园的长椅，黄昏",
    "拼桌的小面馆，下雨天",
    "美术馆的角落，闭馆前",
    "通宵自习室，凌晨",
    "二手market的摊位之间，周末",
    "天台，夏夜",
]


def _style_phrase(p: Persona) -> str:
    """把一个人的 SPEAKS_AS 标签拼成一句风格描述。"""
    tags = sorted(p.style_tags())
    if not tags:
        return "（风格不详）"
    return "、".join(tags)


def _pick_scene(scene_seed: int | None) -> str:
    """从场景池挑一个。给 scene_seed 则确定，否则随机。"""
    if scene_seed is None:
        return random.choice(SCENE_POOL)
    return SCENE_POOL[scene_seed % len(SCENE_POOL)]


# 红线约束 —— 所有推演都必须遵守。设计文档 7.3。
_RED_LINES = """\
【红线 · 必须遵守】
1. 不准出现 AI 腔：不要"作为一个…"、"我理解你的感受"、"让我们一起"这类。
2. 不准泄露系统：对话里不能提"系统"、"算法"、"匹配"、"推荐"、"故知 app"。
   他们就是两个偶然相遇的人，不知道任何"机制"。
3. 不准强行收束：不要在结尾硬塞总结、升华、鸡汤、"我们都…"式的感悟。
   对话可以停在半空中，像真实的相遇一样。
4. 不准编造：只能用下面给的 evidence 原话作为素材，不能捏造他们没说过的
   经历、身份、细节。
5. 各说各的话：A 的台词要像 A 的风格，B 的台词要像 B 的风格，不要混。"""


def _shared_instruction(seed: StorySeed) -> str:
    return f"""\
这是一颗"共鸣种子"：两人在「{seed.cluster}」这个话题上各有心事，
而且心事是相通的。写一段他们偶然聊起、慢慢发现"原来你也"的对话。
不要一上来就点破，让共鸣自然浮现。"""


def _tension_instruction(seed: StorySeed) -> str:
    return f"""\
这是一颗"对立种子"：两人都在意「{seed.cluster}」，但看法相反
（一个偏向「{seed.a_entity}」，一个偏向「{seed.b_entity}」）。
写一段他们因为分歧聊起来的对话 —— 有交锋、有不让步，但又彼此被对方
的视角勾住，不舍得停。不要让谁说服谁，也不要和稀泥。"""


def _supporting_block(a: Persona, b: Persona,
                      supporting_edges: Sequence[SupportingEdge]) -> str:
    """把补充边按 owner 分组,渲染成 prompt 里的一段。

    格式:
        【他们各自的其他心事 —— 也可作为对话里自然带入的素材】
        - {a.name} 还：DISLIKES「PPT 文化」（原话：…）
        - {b.name} 还：LIKES「巴赫」（原话：…）
    """
    if not supporting_edges:
        return ""
    lines = ["", "【他们各自的其他心事 —— 也可作为对话里自然带入的素材】"]
    for se in supporting_edges:
        owner_name = a.name if se.owner == "A" else b.name
        lines.append(
            f"- {owner_name} 还：{se.relation}「{se.entity}」"
            f"（原话：{se.evidence}）"
        )
    return "\n".join(lines)


def build_narration_prompt(seed: StorySeed,
                           a: Persona, b: Persona,
                           scene_seed: int | None = None,
                           supporting_edges: Sequence[SupportingEdge] | None = None,
                           ) -> str:
    """构建推演 prompt。

    给定 scene_seed 时 prompt 完全确定（可重复测试）；否则场景随机。

    supporting_edges (可选): 共簇里的补充边,做"enrich"用。
        None 或空列表 -> prompt 不变 (向后兼容低档 narrator)。
        非空 -> 多一段【他们各自的其他心事】 (供 Sonnet/Opus 笔触更细腻)。
    """
    scene = _pick_scene(scene_seed)

    if seed.seed_type == "CREATIVE_TENSION":
        seed_instruction = _tension_instruction(seed)
    else:
        seed_instruction = _shared_instruction(seed)

    supporting = _supporting_block(a, b, supporting_edges or [])

    return f"""\
你要写一段两个陌生人偶然相遇、聊起来的对话。

【人物】
- {a.name}：说话风格是「{_style_phrase(a)}」
- {b.name}：说话风格是「{_style_phrase(b)}」

【相遇场景】
{scene}

【他们各自的心事 —— 这是你唯一能用的素材】
- {a.name} 说过：「{seed.a_evidence}」（关键词：{seed.a_entity}）
- {b.name} 说过：「{seed.b_evidence}」（关键词：{seed.b_entity}）
{supporting}

【这次相遇的性质】
{seed_instruction}

{_RED_LINES}

【输出要求】
- 6 到 10 轮对话，每轮一句，标明谁说的。
- 中文，口语，符合各自的说话风格。
- 直接输出对话，不要任何前言、解说、标题。"""
