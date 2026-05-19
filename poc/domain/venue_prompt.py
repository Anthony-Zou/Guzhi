"""域层 —— 场地推荐 prompt 构建。

匹配成功之后,基于两人都 LIKES 的具体偏好,生成一段短场地推荐文本。

故知的产品决定写在 prompt 里 (而不是 service 层):
- 不准编造具体商家 (我们不接 O2O 数据,不能让 LLM 装作有数据)
- 不要旅游攻略口吻 ("XX 必去!五星推荐!")
- 不要 dating-app 腔 ("浪漫之选"、"约会胜地")
- 短文本 (两三句),克制
- 鼓励"类型"层面的建议 (如"安静的独立书店"),不要"店名"层面
"""
from __future__ import annotations

from typing import Sequence

from domain.models import Persona


_RED_LINES = """\
【红线】
1. 不准编造具体店名 / 街道 / 大众点评式细节 —— 你没有这些数据。
2. 不要旅游攻略口吻("必去""五星推荐""人均")。
3. 不要 dating-app 腔("浪漫之选""完美约会")。
4. 不要承诺氛围("一定安静""一定不会被打扰") —— 你不知道当天情况。
5. 用建议"类型"的方式 (如"安静的独立书店"、"营业到深夜的小酒馆"),
   不要给具体商家。"""


def build_venue_prompt(a: Persona, b: Persona, *,
                       shared_likes: Sequence[str]) -> str:
    """构建场地推荐 prompt。

    shared_likes: 两人都 LIKES 的 entity 列表 (caller 已经求交集了)。
    """
    if shared_likes:
        likes_block = "他们都喜欢：" + "、".join(shared_likes)
        instruction = (
            "请基于上面这些共同偏好,给一个简短的场地类型建议,"
            "让他们见面时容易找到话题或共同节奏。"
        )
    else:
        likes_block = "（没识别出明显的共同具体偏好）"
        instruction = (
            "他们没有特别明显的共同偏好,你只要写一句话:"
            "「你们也可以先随便约个地方坐坐 —— 共同的话题不在场地里。」"
            "或类似克制的兜底,不要硬推地点。"
        )

    return f"""\
你要给两个匹配上的人,写一段非常短的场地建议。

【他们是谁】
- {a.name}
- {b.name}

【他们的共同点】
{likes_block}

【任务】
{instruction}

{_RED_LINES}

【输出要求】
- 中文,两三句。
- 不要前言、不要总结、不要"祝你们玩得开心"这种结尾。
- 直接输出建议正文。"""
