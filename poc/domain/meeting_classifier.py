"""域层 —— 把"一次相遇"归到三档 narrate call point 之一。

阈值是业务决定:
  score < 0.20:                   NORMAL_MEETING_NARRATE (~75% 相遇)
  0.20 <= score < 0.30:           HIGH_SCORE_MEETING_NARRATE
  score >= 0.20 且有 L3 共簇:     HIGH_SCORE_MEETING_NARRATE
  score >= 0.30 且有 L3 共簇:     L3_PEAK_MEETING_NARRATE (~5%, 灵魂时刻)

这是 pure function:输入分数 + 共簇等级 list,输出 CallPoint。
不依赖 cluster catalog,不依赖 MatchResult 的具体结构。
"""
from __future__ import annotations

from typing import Iterable

from domain.routing import CallPoint


_HIGH_SCORE_THRESHOLD = 0.20
_PEAK_SCORE_THRESHOLD = 0.30


def classify_meeting(score: float, shared_cluster_levels: Iterable[str]) -> str:
    """返回该相遇应该走哪个 narrate 的 CallPoint。

    score: MatchResult.score
    shared_cluster_levels: 共簇的等级列表,例如 ["L3", "L1"]
    """
    has_l3 = "L3" in set(shared_cluster_levels)

    if score < _HIGH_SCORE_THRESHOLD:
        return CallPoint.NORMAL_MEETING_NARRATE

    if score >= _PEAK_SCORE_THRESHOLD and has_l3:
        return CallPoint.L3_PEAK_MEETING_NARRATE

    return CallPoint.HIGH_SCORE_MEETING_NARRATE
