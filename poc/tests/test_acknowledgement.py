"""Tests for domain.acknowledgement.Acknowledgement。

Acknowledgement 是用户投喂之后 agent "回的那一句":
  "这条记下了 · 归到 S2「低谷停撑」"
  "记下了:2 条边,触到了 S2、S3"
  "记下了 (没识别出归属簇,先存着)"

它是一个值对象,带着可选的"渲染成自然语言"的 to_message()。
渲染规则在域层 —— 因为"agent 回什么话"是故知的产品决定 (要保持
克制、不陪聊),不是 IO 细节。
"""
from __future__ import annotations

from domain.acknowledgement import Acknowledgement


class TestStructure:
    def test_fields(self):
        ack = Acknowledgement(
            new_edge_count=2,
            touched_clusters=(("S2", "低谷停撑"), ("S3", "重组中的我")),
            had_noise=False,
        )
        assert ack.new_edge_count == 2
        assert ack.touched_clusters == (("S2", "低谷停撑"), ("S3", "重组中的我"))
        assert ack.had_noise is False


class TestMessageFormat:
    def test_single_cluster_message(self):
        ack = Acknowledgement(
            new_edge_count=1,
            touched_clusters=(("S2", "低谷停撑"),),
            had_noise=False,
        )
        msg = ack.to_message()
        # 含簇名 + 不陪聊 + 简短
        assert "S2" in msg or "低谷停撑" in msg
        assert "低谷停撑" in msg
        # 不该出现陪聊式语气
        assert "我" not in msg or msg.count("我") <= 1
        assert "理解" not in msg
        assert "你的感受" not in msg
        # 简短: < 60 字
        assert len(msg) < 60

    def test_multi_cluster_message_lists_all(self):
        ack = Acknowledgement(
            new_edge_count=3,
            touched_clusters=(
                ("S2", "低谷停撑"),
                ("S3", "重组中的我"),
            ),
            had_noise=False,
        )
        msg = ack.to_message()
        assert "低谷停撑" in msg
        assert "重组中的我" in msg

    def test_no_cluster_hit_says_noted_anyway(self):
        """没归出簇也回一句 —— 让用户知道'记下了',不让 ta 觉得白发。"""
        ack = Acknowledgement(
            new_edge_count=1,
            touched_clusters=(),
            had_noise=True,
        )
        msg = ack.to_message()
        # 含"记下了"或类似的兜底确认
        assert "记下" in msg or "收到" in msg

    def test_zero_edges_says_nothing_added(self):
        """什么都没抽出来时,要诚实告诉用户。"""
        ack = Acknowledgement(
            new_edge_count=0,
            touched_clusters=(),
            had_noise=False,
        )
        msg = ack.to_message()
        # 诚实:不假装"记下了"
        assert "没" in msg or "未" in msg or "无" in msg


class TestImmutable:
    def test_frozen(self):
        ack = Acknowledgement(
            new_edge_count=1,
            touched_clusters=(("S2", "低谷停撑"),),
            had_noise=False,
        )
        import pytest
        with pytest.raises(Exception):
            ack.new_edge_count = 99  # type: ignore[misc]
