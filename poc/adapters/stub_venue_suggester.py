"""adapter —— StubVenueSuggester。

不调 LLM 的占位实现:基于 shared_likes 拼一段确定性文本。
测试 / demo / 没 API key 时用。
"""
from __future__ import annotations

from domain.models import Persona
from domain.shared_likes import compute_shared_likes
from ports.venue_suggester import VenueSuggester


class StubVenueSuggester(VenueSuggester):
    def suggest(self, a: Persona, b: Persona,
                call_point: str | None = None) -> str:
        del call_point
        shared = compute_shared_likes(a, b)
        if not shared:
            return (
                f"{a.name} 和 {b.name} 没识别出明显的共同偏好 —— "
                f"先随便约个地方坐坐都可以,共同的话题不在场地里。"
            )
        joined = "、".join(shared)
        return (
            f"{a.name} 和 {b.name} 都喜欢 {joined}。"
            f"找一个氛围对应的小店,不必是网红地点。"
            f"[此处由真正的 VenueSuggester (Claude/Haiku) 生成更细的建议]"
        )
