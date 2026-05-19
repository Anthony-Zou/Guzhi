"""Tests for domain.events.MeetingEvent —— 一次"两人在小镇相遇"的领域事件。

事件是不可变值对象 (frozen dataclass)。
携带 narrate 需要的所有信息 —— 这样 worker 不必再回查 repo,
也不必再跑一次 match。
"""
from __future__ import annotations

import pytest

from domain.events import MeetingEvent


def _e(**kw):
    """构造一个最小的合法事件。"""
    defaults = dict(
        a_id="P1", b_id="P2",
        score=0.25, shared_clusters=("S2",), shared_levels=("L3",),
        tick=42, sim_run_id="run-x",
    )
    defaults.update(kw)
    return MeetingEvent(**defaults)


class TestMeetingEventStructure:
    def test_carries_all_fields_needed_for_narrate(self):
        e = _e()
        assert e.a_id == "P1"
        assert e.b_id == "P2"
        assert e.score == 0.25
        assert e.shared_clusters == ("S2",)
        assert e.shared_levels == ("L3",)
        assert e.tick == 42
        assert e.sim_run_id == "run-x"

    def test_is_immutable(self):
        e = _e()
        with pytest.raises(Exception):
            e.score = 0.99  # type: ignore[misc]

    def test_event_id_is_stable_and_unique(self):
        """两个相同字段的事件 -> 同 id;不同字段 -> 不同 id。
        这让幂等消费有依据。"""
        a = _e()
        b = _e()
        c = _e(tick=43)
        assert a.event_id == b.event_id
        assert a.event_id != c.event_id


class TestMeetingEventValidation:
    def test_rejects_self_meeting(self):
        with pytest.raises(ValueError):
            _e(a_id="P1", b_id="P1")

    def test_score_must_be_nonneg(self):
        with pytest.raises(ValueError):
            _e(score=-0.1)
