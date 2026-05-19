"""域层 —— 算两人都 LIKES 的 entity 列表。

纯函数。给 venue_prompt 用,以后也可能给"匹配解释卡"用。
"""
from __future__ import annotations

from domain.models import Persona


def compute_shared_likes(a: Persona, b: Persona) -> list[str]:
    """返回两人都 LIKES 的 entity (字典序、去重)。"""
    a_likes = {e.entity for e in a.edges if e.relation == "LIKES"}
    b_likes = {e.entity for e in b.edges if e.relation == "LIKES"}
    return sorted(a_likes & b_likes)
