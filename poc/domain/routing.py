"""域层 —— LLM 调用路由。

故知里 AI 只在两个点出现:
  ① 用户输入 → KG 抽取
  ② 高分相遇 → AI 推演对话

每个点根据"重要性"决定用哪一档模型,这是业务决定,不是基础设施。
所以 router 住在 domain/,只有"call point → tier"的查表逻辑,
完全不知道 anthropic SDK / HTTP / API key 等基础设施细节。

adapter 层负责: tier → 真正的 LLMClient 实例。
"""
from __future__ import annotations

from typing import Mapping


# ────────────────────────────────────────────────────────────────────
# CallPoint —— 调用方靠这些常量描述自己。
# 不用 enum 是为了和 CLAUDE.md 里的 "no enum" 习惯一致 (那条是给
# pixel-agents 的,但保持一致风格也好;轻量地用 as-const 类即可)。
# ────────────────────────────────────────────────────────────────────
class CallPoint:
    """真正消耗 token 的调用点。"""
    # KG 抽取
    ONBOARDING_EXTRACT = "onboarding_extract"
    DAILY_FEED_EXTRACT = "daily_feed_extract"
    # 相遇推演
    NORMAL_MEETING_NARRATE = "normal_meeting_narrate"
    HIGH_SCORE_MEETING_NARRATE = "high_score_meeting_narrate"
    L3_PEAK_MEETING_NARRATE = "l3_peak_meeting_narrate"
    # 配对成功后的场地推荐 (P1.6)
    VENUE_SUGGEST = "venue_suggest"


# ────────────────────────────────────────────────────────────────────
# ModelTier —— 三档抽象。具体模型 ID/单价/SDK 在 adapter 层。
# ────────────────────────────────────────────────────────────────────
class ModelTier:
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


# ────────────────────────────────────────────────────────────────────
# LLMRouter —— 纯查表。
# ────────────────────────────────────────────────────────────────────
class LLMRouter:
    """根据 call point 查 tier。"""

    def __init__(self, routing: Mapping[str, str]) -> None:
        # 显式 copy,防外部修改
        self._routing: dict[str, str] = dict(routing)

    def tier_for(self, call_point: str) -> str:
        """返回该 call point 应该走的 ModelTier。未配置则抛 KeyError。"""
        return self._routing[call_point]


# ────────────────────────────────────────────────────────────────────
# DEFAULT_ROUTING —— PHASE2_BACKLOG 里定下的默认配置。
# 改这里 = 改路由策略。改完测试会兜底:数字会自动反映到成本表实测。
# ────────────────────────────────────────────────────────────────────
DEFAULT_ROUTING: Mapping[str, str] = {
    # 抽取
    CallPoint.ONBOARDING_EXTRACT:        ModelTier.SONNET,  # 决定 KG 起点质量
    CallPoint.DAILY_FEED_EXTRACT:        ModelTier.HAIKU,   # 增量短文本

    # 推演
    CallPoint.NORMAL_MEETING_NARRATE:    ModelTier.HAIKU,   # ~75% 相遇
    CallPoint.HIGH_SCORE_MEETING_NARRATE: ModelTier.SONNET, # ~15-20% 相遇
    CallPoint.L3_PEAK_MEETING_NARRATE:    ModelTier.OPUS,   # ~5% 灵魂时刻

    # 场地推荐 (P1.6) —— 只在 high-score 匹配成功后触发,体量小
    CallPoint.VENUE_SUGGEST:              ModelTier.HAIKU,  # 不该烧 Sonnet
}
