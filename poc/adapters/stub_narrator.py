"""adapter — StubNarrator。

实现 Narrator 端口，但不真调 AI。POC 阶段用它验证"种子 -> 推演"这条链路接通。
以后写一个 ClaudeNarrator（同样实现 Narrator 端口）即可无缝替换，
领域逻辑一行都不用改 —— 这就是六边形架构的价值。
"""
from __future__ import annotations

from domain.models import Persona
from domain.seeds import StorySeed
from ports.narrator import Narrator


class StubNarrator(Narrator):
    """假推演器：把种子格式化成一段占位文本，不调用任何 AI。"""

    def narrate(self, seed: StorySeed, a: Persona, b: Persona,
                call_point: str | None = None,
                shared_clusters: tuple[str, ...] | None = None) -> str:
        # 对 stub 都没用 —— 它不调真 LLM 也不 enrich
        del call_point, shared_clusters
        if seed.seed_type == "CREATIVE_TENSION":
            head = f"【对立种子 · {seed.cluster}】"
            hook = (f"{a.name} 觉得「{seed.a_entity}」，"
                    f"{b.name} 却觉得「{seed.b_entity}」——同一件事，相反的看法。")
        else:
            head = f"【共鸣种子 · {seed.cluster}】"
            hook = (f"{a.name} 和 {b.name} 都在「{seed.a_entity}」"
                    f"这件事上停留。")

        return (
            f"{head}\n"
            f"{hook}\n"
            f"  {a.name} 的原话：{seed.a_evidence}\n"
            f"  {b.name} 的原话：{seed.b_evidence}\n"
            f"  [此处由真正的 Narrator (Claude) 生成 6-10 轮对话]"
        )
