"""Tests for domain.meeting_classifier ——
根据相遇的分数和共簇等级,把相遇分类为 NORMAL / HIGH_SCORE / L3_PEAK。

阈值是业务决定 (domain),不是基础设施。所以放 domain/。
和 PHASE2_BACKLOG 里的占比 (~75% / ~20% / ~5%) 大致对得上。

设计:函数只接受最小输入 —— score 和 levels list。
不绑死 MatchResult 的结构,也不依赖 cluster catalog。
caller 用 MatchResult.score + 把 shared_clusters 翻译成 levels 列表即可。
"""
from __future__ import annotations

from domain.meeting_classifier import classify_meeting
from domain.routing import CallPoint


class TestClassifier:
    def test_low_score_is_normal(self):
        assert classify_meeting(0.10, ["L1"]) == CallPoint.NORMAL_MEETING_NARRATE

    def test_mid_score_is_normal(self):
        assert classify_meeting(0.18, ["L1", "L2"]) == CallPoint.NORMAL_MEETING_NARRATE

    def test_high_score_no_l3_is_high(self):
        """高分但不带 L3,算高分相遇但不是顶峰。"""
        assert classify_meeting(0.35, ["L1", "L2"]) == CallPoint.HIGH_SCORE_MEETING_NARRATE

    def test_high_score_with_l3_is_peak(self):
        """高分 + L3 共簇 = 灵魂时刻。"""
        assert classify_meeting(0.40, ["L3", "L1"]) == CallPoint.L3_PEAK_MEETING_NARRATE

    def test_low_score_with_l3_is_normal(self):
        """只有 L3 但分数没到,不算 peak —— 数据不足够。"""
        assert classify_meeting(0.12, ["L3"]) == CallPoint.NORMAL_MEETING_NARRATE

    def test_no_shared_clusters_is_normal(self):
        """空 levels(理论上不该出现,但容错)走 normal。"""
        assert classify_meeting(0.15, []) == CallPoint.NORMAL_MEETING_NARRATE


class TestThresholds:
    def test_normal_high_boundary(self):
        """0.20 是 normal/high 的边界(<0.20 normal, >=0.20 high)。"""
        assert classify_meeting(0.199, ["L1"]) == CallPoint.NORMAL_MEETING_NARRATE
        assert classify_meeting(0.200, ["L2"]) == CallPoint.HIGH_SCORE_MEETING_NARRATE

    def test_high_peak_boundary(self):
        """0.30 + L3 是 high/peak 的边界。"""
        assert classify_meeting(0.299, ["L3"]) == CallPoint.HIGH_SCORE_MEETING_NARRATE
        assert classify_meeting(0.300, ["L3"]) == CallPoint.L3_PEAK_MEETING_NARRATE
