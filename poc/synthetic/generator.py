"""合成数据生成器。

从一个"特质库"组合出人物。真值表是组合规则的机械产物。

防作弊设计：
- 生成器判定"该不该匹配"用简单的**集合计数规则**（_should_match）
- 匹配算法（domain/matching.py）用带 strength/normalize/深度加权的**打分**
两者逻辑不同。若算法结果能复现生成器的真值表，才说明算法的复杂打分有效。

这个模块属于"测试夹具"性质，不是产品代码，因此可以依赖 domain。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from domain.models import Edge, Persona, Cluster, ClusterLevel


# ============================================================
# 姓名库 —— 给合成人物配真人名（中文，男女各半）
# ============================================================

_SURNAMES = [
    # 主流 + 一些更有小说感的姓 (沈/苏/江/温/陆/裴/谢/卫/姜/秦/顾/池)
    "陈", "林", "周", "黄", "吴", "刘", "张", "王", "李", "赵",
    "孙", "杨", "徐", "胡", "朱", "高", "郭", "何", "罗", "宋",
    "沈", "苏", "江", "温", "陆", "裴", "谢", "卫", "姜", "秦",
    "顾", "池", "云", "傅", "霍", "白", "唐", "韩", "钟", "齐",
]
# 男主名字池 —— 文气、克制、有故事感,不浮夸
_GIVEN_MALE = [
    "砚之", "言之", "知行", "怀瑾", "止戈", "亦舟", "云深",
    "听澜", "予安", "牧之", "执一", "景行", "鸿渐", "屿白",
    "衍之", "明烛", "如晦", "西沉", "之桓", "渡之", "知秋",
    "时砚", "暮迟", "玉书", "南川", "野舟", "寻欢", "归之",
    "无咎", "见南", "敛之", "怀远", "予清", "扶光", "南屿",
    "守拙", "嘉树", "怀瑜", "九思", "白也", "知非", "止水",
    "齐桓", "迟野", "之昂", "归舟", "向晚", "言行", "未济",
]
# 女主名字池
_GIVEN_FEMALE = [
    "见微", "知微", "南乔", "栖迟", "若安", "未眠", "之遥",
    "拾光", "因之", "疏桐", "清禾", "宛之", "亦柔", "宁谧",
    "晚晴", "归棠", "予舟", "瑟瑟", "颂今", "野晴", "时予",
    "云迟", "知岁", "明栖", "若鸿", "渡棠", "倦倦", "南萤",
    "未央", "晚照", "听潮", "予乔", "归砚", "拾月", "知白",
    "云栖", "微澜", "迟予", "似锦", "南溪", "予以", "知止",
    "归宁", "拂衣", "明远", "棠予", "守静", "如砚",
]

# ── 英文人物池(切到 EN 时用) ────────────────────────────
# 不音译,挑文气 + 中性现代 + 有故事感的英文名。
# 故意没用 Ashton / Brandon 这种太常见的;故事感优先。
_SURNAMES_EN = [
    "Reyes", "Mori", "Vale", "Crane", "Lane", "Quinn", "Hart",
    "Wren", "Bauer", "Greer", "Holt", "Marsh", "Frost", "Sinclair",
    "Auerbach", "Sato", "Aoki", "Lin", "Chen", "Park",
    "Castellan", "Nakamura", "Solberg", "Okafor", "Bose",
    "Iqbal", "Reinhart", "Donatelli", "Voss", "Tassi",
    "Hadid", "Selva", "Rivera", "Khan", "Park",
    "Yu", "Zhao", "Hsiao", "Park", "Adell",
]
_GIVEN_MALE_EN = [
    "Eli", "Caspar", "Lior", "Auden", "Theo", "Soren", "Felix",
    "Casimir", "Ambrose", "Levi", "Roman", "Jasper", "Silas",
    "Reza", "Mateo", "Yusuf", "Hugo", "Anders", "Cyrus",
    "Tobias", "Linus", "Emil", "Hayao", "Idris", "Nico",
    "Asher", "Otto", "Atlas", "Wilder", "Beck", "Rune",
    "Kohaku", "Adrien", "Damian", "Elias", "Aramis", "Quill",
    "Inigo", "Renzo", "Sage", "Aurelio", "Aiden", "Lior",
    "Jonas", "Orlando", "Cassian", "Henrik", "Mateusz",
]
_GIVEN_FEMALE_EN = [
    "June", "Mira", "Liva", "Anwen", "Ines", "Saoirse", "Lyra",
    "Imani", "Eira", "Nadia", "Wren", "Vera", "Yuki", "Ruth",
    "Cleo", "Naoko", "Theia", "Iris", "Phaedra", "Anya",
    "Maren", "Sofie", "Tova", "Briar", "Nori", "Linnea",
    "Esme", "Tamsin", "Maia", "Niamh", "Yael", "Vesper",
    "Marit", "Hadley", "Sigrid", "Yana", "Mio", "Soraya",
    "Lila", "Astrid", "Inanna", "Reema", "Ondine", "Calla",
    "Sennen", "Halia", "Ines",
]


# ============================================================
# 特质库
# ============================================================

@dataclass(frozen=True)
class TraitLibrary:
    """特质库：簇定义 + 每个簇下的可选 entity + 噪音 entity 池。"""
    clusters: dict[str, Cluster]
    cluster_entities: dict[str, list[str]]           # cid -> [entity, ...]
    cluster_relation: dict[str, str]                 # cid -> 这些 entity 用什么 relation
    cluster_label: dict[str, str]                    # cid -> 人物标签（用于给人物起语义名）
    noise_entities: list[tuple[str, str]]            # [(relation, entity), ...]
    tension_pairs: list[tuple[str, str, str]]
    style_tags: list[str]
    style_complement_pairs: list[tuple[str, str]]
    # i18n: 簇名 / 标签的英文映射(可选,前端切 EN 时取)
    cluster_name_en: dict[str, str] = field(default_factory=dict)
    cluster_label_en: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def default() -> "TraitLibrary":
        clusters = {
            # L3 存在性议题
            "S1": Cluster("S1", "去留之惑", ClusterLevel.L3, "feeling_resonance"),
            "S2": Cluster("S2", "低谷停撑", ClusterLevel.L3, "feeling_resonance"),
            "S3": Cluster("S3", "自我认同重组", ClusterLevel.L3, "belief_alignment"),
            "S4": Cluster("S4", "意义之问", ClusterLevel.L3, "feeling_resonance"),
            # L2 价值观
            "S5": Cluster("S5", "反效率主义", ClusterLevel.L2, "belief_alignment"),
            "S6": Cluster("S6", "形式之美", ClusterLevel.L2, "belief_alignment"),
            "S7": Cluster("S7", "独立自主", ClusterLevel.L2, "belief_alignment"),
            "S8": Cluster("S8", "诚实至上", ClusterLevel.L2, "belief_alignment"),
            # L1 偏好
            "S9": Cluster("S9", "反正能量表演", ClusterLevel.L1, "shared_aversion"),
            "S10": Cluster("S10", "文艺电影品味", ClusterLevel.L1, "shared_passion"),
            "S11": Cluster("S11", "户外行动派", ClusterLevel.L1, "shared_passion"),
            "S12": Cluster("S12", "古典音乐", ClusterLevel.L1, "shared_passion"),
        }
        # A：每个簇的 entity 库扩到 ~10 个，让人物组合更多样。
        # 注意：只扩广度，不改簇结构、不改 relation —— 不影响匹配算法和真值表规则。
        cluster_entities = {
            "S1": ["要不要回老家", "留下还是离开", "要不要换个城市",
                   "这座城市还值不值得待", "回去算不算认输",
                   "异乡待久了算不算家", "该不该为了人留下",
                   "走了会不会后悔", "在哪都像过客", "落脚的地方到底在哪"],
            "S2": ["该不该停下来歇歇", "是不是快撑不住了",
                   "能不能不再怕复发", "状态很差但不敢停",
                   "需要一个喘息的理由", "停下来会不会就起不来了",
                   "撑着的意义是什么", "想躺平又怕真的废掉",
                   "怎么判断是累还是病了", "什么时候才能不紧绷"],
            "S3": ["我好像不是原来的我了", "当了妈妈之后还是不是我自己",
                   "离职后才发现真正想要的", "我到底是哪个版本的自己",
                   "身份变了内核还在不在", "别人眼里的我和我自己差很远",
                   "过去的标签还算不算数", "换了环境我还是我吗",
                   "想重新定义自己又怕推翻一切", "成长是不是在丢掉旧的我"],
            "S4": ["做这些到底有没有意义", "忙碌是不是在逃避",
                   "成功之后然后呢", "我在为谁活",
                   "重要的事到底是什么", "努力的尽头是什么",
                   "热闹之后的空虚感", "如果没人看见还做不做",
                   "什么值得用一生去换", "意义是找到的还是给出的"],
            "S5": ["人不该被KPI量化", "效率不是最高价值",
                   "慢下来不是错", "加班崇拜很有毒",
                   "人不需要一直证明自己", "产出不等于价值",
                   "把人当工具是错的", "忙不等于有用",
                   "拒绝把生活外包给工作", "时间不该全用来变现"],
            "S6": ["数学证明之美", "简洁代码的优雅", "工具应该boring才好",
                   "克制的设计最美", "形式本身就是内容",
                   "少即是多", "结构之美高于装饰",
                   "好东西不需要解释", "精确本身令人安心",
                   "对粗糙的容忍度很低"],
            "S7": ["不依附任何机构", "自己定义成功", "不需要被认可",
                   "独处是必需品", "拒绝被安排的人生",
                   "我的节奏我自己定", "不喜欢被纳入任何体系",
                   "自由比安稳重要", "选择权比结果重要",
                   "宁可孤独也不将就"],
            "S8": ["讨厌一切伪装", "宁可难听也要真话", "诚实的失败也值得",
                   "不说自己不信的话", "真实比体面重要",
                   "受不了客套和场面话", "宁可冒犯也不虚伪",
                   "坦白是一种尊重", "假装积极很累",
                   "把话说清楚比说漂亮重要"],
            "S9": ["积极心理学话术", "职场正能量", "过度热情的客套",
                   "强行打鸡血", "表演式的乐观",
                   "苦难叙事包装", "把焦虑说成上进",
                   "朋友圈式人设", "成功学口号", "情绪劳动被当成美德"],
            "S10": ["黑泽明", "侯孝贤", "蔡明亮", "小津安二郎", "贾樟柯",
                    "杨德昌", "是枝裕和", "王家卫", "塔可夫斯基", "毕赣"],
            "S11": ["徒步登山", "长跑", "攀岩", "骑行", "野外露营",
                    "越野跑", "桨板", "滑雪", "潜水", "城市暴走"],
            "S12": ["巴赫", "马勒", "肖邦", "德彪西", "勃拉姆斯",
                    "拉赫玛尼诺夫", "舒伯特", "西贝柳斯", "拉威尔", "肖斯塔科维奇"],
        }
        cluster_relation = {
            "S1": "FEELS_NOW", "S2": "FEELS_NOW", "S3": "FEELS_NOW",
            "S4": "FEELS_NOW",
            "S5": "BELIEVES", "S6": "BELIEVES", "S7": "BELIEVES",
            "S8": "BELIEVES",
            "S9": "DISLIKES", "S10": "LIKES", "S11": "LIKES", "S12": "LIKES",
        }
        # 每个簇配一个"人物标签"，用于给合成人物起语义化的画像
        cluster_label = {
            "S1": "去留之间",     # 去留之惑
            "S2": "低谷里的人",   # 低谷停撑
            "S3": "重组中的我",   # 自我认同重组
            "S4": "追问意义者",   # 意义之问
            "S5": "反内卷者",     # 反效率主义
            "S6": "形式之美的信徒",  # 形式之美
            "S7": "独行者",       # 独立自主
            "S8": "诚实派",       # 诚实至上
            "S9": "反鸡汤的人",   # 反正能量表演
            "S10": "文艺片影迷",  # 文艺电影品味
            "S11": "户外行动派",  # 户外行动派
            "S12": "古典乐迷",    # 古典音乐
        }
        # B：噪音边池扩到 ~28 个。噪音边不进簇、不进匹配，
        # 加多少都不影响验证 —— 它的作用只是让人物的"边集合"更真实、更杂。
        noise_entities = [
            ("EXPERIENCED", "在三个城市生活过"),
            ("EXPERIENCED", "换过两次行业"),
            ("EXPERIENCED", "读过研究生"),
            ("EXPERIENCED", "创业失败过一次"),
            ("EXPERIENCED", "独自旅行过"),
            ("EXPERIENCED", "经历过重大挫折后重建"),
            ("EXPERIENCED", "从稳定工作转向自由职业"),
            ("EXPERIENCED", "长期坚持一项小众爱好"),
            ("EXPERIENCED", "参与过社会公益活动"),
            ("EXPERIENCED", "异地恋过几年"),
            ("EXPERIENCED", "照顾过生病的家人"),
            ("EXPERIENCED", "搬过很多次家"),
            ("LIKES", "做饭"),
            ("LIKES", "养猫"),
            ("LIKES", "手冲咖啡"),
            ("LIKES", "旧书店"),
            ("LIKES", "下雨天听音乐"),
            ("LIKES", "观察陌生人的生活"),
            ("LIKES", "收集地图"),
            ("LIKES", "深夜散步"),
            ("LIKES", "二手市集"),
            ("LIKES", "写手账"),
            ("DISLIKES", "早起"),
            ("DISLIKES", "无效会议"),
            ("DISLIKES", "排队等待"),
            ("DISLIKES", "被无故打断"),
            ("DISLIKES", "群体合影"),
            ("DISLIKES", "电话推销"),
        ]
        tension_pairs = [
            ("S10", "黑泽明", "侯孝贤"),  # 同属文艺电影但风格取向差异
        ]
        style_tags = [
            "冷面笑匠", "文艺抒情", "直球简洁", "学术理性", "温柔细腻",
            "锐利批判", "慵懒散漫", "紧凑高密度", "激昂热烈", "平静温和",
            "神秘留白", "具象画面", "抽象思辨", "怀旧调性",
        ]
        style_complement_pairs = [
            ("锐利批判", "温柔细腻"),
            ("紧凑高密度", "慵懒散漫"),
            ("激昂热烈", "平静温和"),
            ("抽象思辨", "具象画面"),
        ]
        # i18n: 簇名 / 标签的英文版。手写,不机翻 —— 文气保住。
        cluster_name_en = {
            "S1": "Stay or leave",
            "S2": "Holding on through the trough",
            "S3": "Reassembling the self",
            "S4": "Asking what for",
            "S5": "Anti-efficiency",
            "S6": "The beauty of form",
            "S7": "On one's own terms",
            "S8": "Honesty above all",
            "S9": "Against performative positivity",
            "S10": "Slow-cinema taste",
            "S11": "Out where the wind is",
            "S12": "Classical music",
        }
        cluster_label_en = {
            "S1": "the one in between",
            "S2": "the one holding on",
            "S3": "the one reassembling",
            "S4": "the one who asks why",
            "S5": "the one who refuses the grind",
            "S6": "the one who loves form",
            "S7": "the one walking alone",
            "S8": "the honest one",
            "S9": "allergic to fake positivity",
            "S10": "the slow-cinema watcher",
            "S11": "the one outside",
            "S12": "the classical listener",
        }
        return TraitLibrary(
            clusters=clusters,
            cluster_entities=cluster_entities,
            cluster_relation=cluster_relation,
            cluster_label=cluster_label,
            noise_entities=noise_entities,
            tension_pairs=tension_pairs,
            style_tags=style_tags,
            style_complement_pairs=style_complement_pairs,
            cluster_name_en=cluster_name_en,
            cluster_label_en=cluster_label_en,
        )


# ============================================================
# 生成器
# ============================================================

class PersonaGenerator:
    def __init__(self, library: TraitLibrary, seed: int = 0) -> None:
        self._lib = library
        # 两个独立的随机数流：
        # _trait_rng 决定人物的特质（簇、边、强度）—— 这是匹配的输入
        # _name_rng  决定姓名和性别 —— 纯展示信息
        # 隔离的原因：加 / 改姓名逻辑不应改变底层特质数据，
        # 否则同一个 seed 会生成不同的人，破坏可复现性和已有验证。
        self._trait_rng = random.Random(seed)
        self._name_rng = random.Random(seed + 100000)
        # EN 名字用独立 rng,这样加入 EN 名字生成不会扰乱 ZH 性别分布
        self._name_en_rng = random.Random(seed + 200000)
        # 已用过的姓名集合,_human_name 内部去重 —— 保证 30 人小镇内无重名
        self._used_names: set[str] = set()
        self._used_names_en: set[str] = set()
        # pid -> 对应的英文名(随 ZH 名一起生成,持久映射)
        self._en_name_by_pid: dict[str, str] = {}

    def generate(self, count: int) -> list[Persona]:
        """生成指定数量的合成人物。"""
        personas = []
        for i in range(count):
            personas.append(self._generate_one(i))
        return personas

    def _generate_one(self, index: int) -> Persona:
        """生成单个合成人物。"""
        rng = self._trait_rng
        lib = self._lib

        # 抽 2-4 个簇
        n_clusters = rng.randint(2, 4)
        chosen_clusters = rng.sample(list(lib.clusters.keys()), n_clusters)

        edges: list[Edge] = []

        # 为每个选中的簇添加边
        for cid in chosen_clusters:
            relation = lib.cluster_relation[cid]
            # 每个簇抽 1-2 个 entity
            n_ent = rng.randint(1, 2)
            ents = rng.sample(lib.cluster_entities[cid],
                              min(n_ent, len(lib.cluster_entities[cid])))
            for ent in ents:
                strength = round(rng.uniform(0.65, 0.95), 2)
                edges.append(Edge(
                    relation=relation,
                    entity=ent,
                    strength=strength,
                    cluster=cid,
                    evidence=f"（合成）{ent}",
                ))

        # 加 1-3 条噪音边
        n_noise = rng.randint(1, 3)
        for relation, ent in rng.sample(lib.noise_entities,
                                        min(n_noise, len(lib.noise_entities))):
            edges.append(Edge(
                relation=relation,
                entity=ent,
                strength=round(rng.uniform(0.5, 0.85), 2),
                cluster=None,
                evidence=f"（合成噪音）{ent}",
            ))

        # 加 2-3 个风格标签
        n_style = rng.randint(2, 3)
        for tag in rng.sample(lib.style_tags, n_style):
            edges.append(Edge(
                relation="SPEAKS_AS",
                entity=tag,
                strength=round(rng.uniform(0.6, 0.9), 2),
                cluster=None,
                evidence=f"（合成风格）{tag}",
            ))

        pid = f"SYN{index + 1:02d}"
        # 姓名 / 性别用独立的 _name_rng，不污染特质随机流
        name_rng = self._name_rng
        gender = name_rng.choice(["male", "female"])
        name = self._human_name(name_rng, gender)
        # 同时生成一个英文名,记到 pid -> name_en 字典里;EN UI 时取
        # 用独立 rng 不污染 ZH 流
        self._en_name_by_pid[pid] = self._human_name_en(self._name_en_rng, gender)
        archetype = self._archetype(chosen_clusters)
        return Persona(id=pid, name=name, edges=tuple(edges),
                       gender=gender, archetype=archetype)

    def name_en_for(self, pid: str) -> str:
        """返回该 pid 对应的英文名。需要先 generate() 过。"""
        return self._en_name_by_pid.get(pid, pid)

    def _human_name(self, rng: random.Random, gender: str) -> str:
        """生成一个中文真人名,与性别匹配,且在一次 generate() 内不重名。

        重名虽然现实里会有,但在 30 人合成小镇里看起来是 bug。
        组合空间足够大 (40 姓 × 34 名 = 1360),去重几乎不会拖慢。

        如果池真的耗尽,降级回到加数字后缀的兜底版本。
        """
        surname_pool = _SURNAMES
        given_pool = _GIVEN_MALE if gender == "male" else _GIVEN_FEMALE
        # 最多尝试 50 次找一个没用过的;够安全
        for _ in range(50):
            candidate = rng.choice(surname_pool) + rng.choice(given_pool)
            if candidate not in self._used_names:
                self._used_names.add(candidate)
                return candidate
        # 池子真的耗尽 —— 加数字后缀兜底
        fallback = rng.choice(surname_pool) + rng.choice(given_pool)
        i = 2
        while f"{fallback}·{i}" in self._used_names:
            i += 1
        result = f"{fallback}·{i}"
        self._used_names.add(result)
        return result

    def _human_name_en(self, rng: random.Random, gender: str) -> str:
        """生成一个英文名,format: 'Given Surname'。同样在 batch 内去重。"""
        given_pool = _GIVEN_MALE_EN if gender == "male" else _GIVEN_FEMALE_EN
        for _ in range(50):
            candidate = rng.choice(given_pool) + " " + rng.choice(_SURNAMES_EN)
            if candidate not in self._used_names_en:
                self._used_names_en.add(candidate)
                return candidate
        # 池耗尽兜底
        fallback = rng.choice(given_pool) + " " + rng.choice(_SURNAMES_EN)
        i = 2
        while f"{fallback} {i}" in self._used_names_en:
            i += 1
        result = f"{fallback} {i}"
        self._used_names_en.add(result)
        return result

    def _archetype(self, chosen_clusters: list[str]) -> str:
        """生成这个人的'特质画像' —— 之前冒充 name 的两簇标签。

        格式：<最深簇标签>·<第二深簇标签>，如 "去留之间·低谷里的人"。
        这是展示信息，给可视化和详情面板用，不参与匹配。

        确定性：chosen_clusters 抽取顺序固定，stable sort，同 seed 同结果。
        """
        lib = self._lib
        level_rank = {ClusterLevel.L3: 0, ClusterLevel.L2: 1, ClusterLevel.L1: 2}
        ordered = sorted(
            chosen_clusters,
            key=lambda cid: level_rank[lib.clusters[cid].level],
        )
        if len(ordered) >= 2:
            labels = [lib.cluster_label[cid] for cid in ordered[:2]]
            return "·".join(labels)
        if len(ordered) == 1:
            return lib.cluster_label[ordered[0]]
        return "特质不明"


# ============================================================
# 真值表 —— 机械规则的产物
# ============================================================

def _should_match(a_clusters: set[str], b_clusters: set[str],
                  library: TraitLibrary) -> bool:
    """生成器的'设计意图'判定规则。

    规则（独立于匹配算法）：
      - 共享 >= 1 个 L3 簇 -> 该匹配
      - 共享 >= 2 个任意簇 -> 该匹配
      - 否则不该匹配
    """
    shared = a_clusters & b_clusters
    if not shared:
        return False

    l3_shared = [cid for cid in shared
                 if library.clusters[cid].level == ClusterLevel.L3]
    if len(l3_shared) >= 1:
        return True
    if len(shared) >= 2:
        return True
    return False


def ground_truth_for(personas: list[Persona],
                     library: TraitLibrary) -> dict[str, set[str]]:
    """对一组人物，机械地算出真值表。

    返回 {pid: set(应该匹配的 pid)}，对称。
    """
    truth: dict[str, set[str]] = {p.id: set() for p in personas}
    for i in range(len(personas)):
        for j in range(i + 1, len(personas)):
            a, b = personas[i], personas[j]
            if _should_match(a.clusters_present(),
                             b.clusters_present(), library):
                truth[a.id].add(b.id)
                truth[b.id].add(a.id)
    return truth
