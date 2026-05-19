"""domain 层 — 抽取 prompt 构建。

纯函数，零外部依赖。把"自述文本 + 簇定义"转成给 LLM 的抽取 prompt。

prompt 要告诉 LLM：
  - 有哪些语义簇，每个簇是什么意思，示例 entity 是什么粒度
  - 抽成什么 JSON 格式
  - strength 怎么定（语气强度）
  - 不准编造（只抽文本里真有的）

prompt 的"设计"是领域知识，所以放 domain 层。调 LLM 在 adapters。
"""
from __future__ import annotations


# cluster_guide 的类型：cluster_id -> (簇名, [示例 entity, ...])
ClusterGuide = dict[str, tuple[str, list[str]]]


def _format_cluster_guide(guide: ClusterGuide) -> str:
    """把簇定义格式化成 prompt 里的一段说明。"""
    lines = []
    for cid in sorted(guide):
        name, examples = guide[cid]
        ex = "、".join(examples)
        lines.append(f"  - {cid}「{name}」：例如 {ex}")
    return "\n".join(lines)


def build_extraction_prompt(text: str, cluster_guide: ClusterGuide) -> str:
    """构建抽取 prompt。同输入同输出（纯函数）。"""
    cluster_section = _format_cluster_guide(cluster_guide)

    return f"""\
你要从一段自述文本里，抽取出这个人的"知识图谱边"。

【自述文本】
{text}

【可用的语义簇】
每条边要尽量归到下面某个簇。簇代表"这个人在某个深层主题上有心事/有立场"：
{cluster_section}

【抽取规则】
1. 只抽文本里**真实出现**的内容。不准编造、不准脑补文本没说的经历或立场。
2. 每条边包含四个字段：
   - relation：FEELS_NOW（当下心事）/ BELIEVES（信念立场）/
     LIKES（喜欢）/ DISLIKES（讨厌）/ EXPERIENCED（经历过）/
     SPEAKS_AS（说话风格）
   - entity：一个简短的关键词短语（参考上面簇里的示例粒度）
   - strength：0.0–1.0。语气越强烈、越笃定，分越高；
     一笔带过的给 0.5 左右；非常强烈（"特别"、"一直"、"绝对"）给 0.8+。
   - cluster：归到的簇 id（如 S1）。如果这条边不属于任何上面的簇，
     cluster 填 null（它会成为"噪音边"，保留但不参与匹配）。
3. evidence 字段：摘录文本里支持这条边的原话片段。

【输出格式】
严格输出 JSON，形如：
{{
  "edges": [
    {{"relation": "FEELS_NOW", "entity": "要不要回老家",
      "strength": 0.85, "cluster": "S1",
      "evidence": "我最近一直在想要不要回老家"}}
  ]
}}
只输出 JSON，不要任何前言或解说。"""
