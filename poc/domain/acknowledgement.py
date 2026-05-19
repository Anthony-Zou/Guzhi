"""域层 —— 投喂回执 Acknowledgement。

用户投喂之后,agent 回的那一句确认。

故知的产品决定:agent 不主动陪聊。投喂之后只给一句"记下了 · 归到 ..."
让用户感觉 ta 在长,而不是 ta 在替代真人。

这条规则在域层 (不在 UI 层),因为:
- 这是产品/品牌核心约束,不是显示细节
- 同一规则在 web / mobile / API 都得遵守
- 改这条 = 改"故知是什么"
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Acknowledgement:
    """投喂回执。值对象,带渲染逻辑。

    Attributes:
        new_edge_count: 这次投喂新合并进 KG 的边数 (max 取后)
        touched_clusters: 被命中的簇 [(cluster_id, cluster_name), ...]
                          按 cluster_id 字典序;若有重复在调用方先去重
        had_noise: 是否抽出过 cluster=None 的"噪音边" (用于让 ack 措辞
                   更诚实:"没识别出簇,先存着")
    """
    new_edge_count: int
    touched_clusters: tuple[tuple[str, str], ...]
    had_noise: bool

    def to_message(self) -> str:
        """渲染成给用户看的那一句。

        三档语气 (按内容自动选):
          - 没新边 -> "这次没记到新东西。"
          - 有新边但无簇 -> "记下了。 (没归出簇)"
          - 有新边 + 有簇 -> "记下了 · 归到 S2「低谷停撑」"
                            多簇: "记下了 · 归到 S2「…」、S3「…」"
        """
        if self.new_edge_count == 0:
            return "这次没记到新东西。"

        if not self.touched_clusters:
            return "记下了。 (没归出簇,先存着)"

        cluster_strs = [
            f"{cid}「{name}」"
            for cid, name in self.touched_clusters
        ]
        return "记下了 · 归到 " + "、".join(cluster_strs)
