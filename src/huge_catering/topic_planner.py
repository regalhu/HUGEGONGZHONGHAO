from __future__ import annotations

from dataclasses import asdict, dataclass
import random


TARGET_READER = "中小餐饮老板、餐饮店长、餐饮创业者"

WRITING_ANGLES = [
    "客流角度",
    "客单价角度",
    "毛利角度",
    "复购角度",
    "用户体验角度",
    "门店执行角度",
    "老板决策角度",
    "员工管理角度",
    "菜单结构角度",
    "成本控制角度",
    "加盟管控角度",
    "品牌长期主义角度",
]

TEN_LESSONS_TOPICS = [
    "成本控制",
    "菜单优化",
    "员工管理",
    "外卖运营",
    "顾客复购",
    "开店选址",
    "门店卫生",
    "老板心态",
    "加盟管理",
    "产品定价",
    "会员运营",
    "社群运营",
    "新品推广",
    "差评处理",
    "门店动线",
    "高峰期出餐",
    "损耗管理",
    "供应链管理",
    "店长带教",
    "门店标准化",
]

METHODOLOGY_TOPICS = [
    "菜单越做越乱怎么办",
    "高毛利菜卖不动怎么办",
    "门店客流下降怎么办",
    "外卖单量上不去怎么办",
    "顾客来了不复购怎么办",
    "员工执行力差怎么办",
    "店长不会带团队怎么办",
    "新品上市没声量怎么办",
    "团购套餐不赚钱怎么办",
    "加盟店不听总部标准怎么办",
    "门店评分下降怎么办",
    "高峰期出餐慢怎么办",
    "原材料损耗高怎么办",
    "老板每天很忙但利润很低怎么办",
    "小店不知道怎么做私域怎么办",
]

HOT_SUBTOPICS = [
    ("对门店客流的影响", "客流角度", "不要写毛利结构"),
    ("对毛利结构的影响", "毛利角度", "不要写客流变化"),
    ("对价格带和客单价的影响", "客单价角度", "不要写堂食体验"),
    ("对堂食体验的影响", "用户体验角度", "不要写会员复购"),
    ("对会员复购和私域的影响", "复购角度", "不要写价格战风险"),
    ("对小店价格战风险的影响", "老板决策角度", "不要写客流变化"),
    ("对菜单结构的影响", "菜单结构角度", "不要写员工管理"),
    ("对门店执行动作的影响", "门店执行角度", "不要写品牌长期主义"),
    ("对员工排班和话术的影响", "员工管理角度", "不要写供应链成本"),
    ("对品牌长期主义的影响", "品牌长期主义角度", "不要写短期促销"),
]


@dataclass(frozen=True)
class TopicPlan:
    topic: str
    angle: str
    target_reader: str = TARGET_READER
    avoid_repeat_point: str = ""
    keyword: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def topic_planner(
    *,
    keyword: str | None,
    article_type: str,
    count: int = 5,
    seed: int | None = None,
) -> list[TopicPlan]:
    clean_keyword = str(keyword or "").strip()
    target_count = max(1, min(10, int(count or 5)))
    if article_type == "hot_interpretation":
        if not clean_keyword:
            return []
        return _hot_plans(clean_keyword, target_count)
    if article_type == "methodology":
        return _methodology_plans(clean_keyword, target_count, seed=seed)
    return _ten_lessons_plans(clean_keyword, target_count, seed=seed)


def build_article_prompt(*, article_type: str, plan: TopicPlan) -> str:
    return "\n".join(
        [
            f"当前文章类型：{article_type}",
            f"当前文章主题：{plan.topic}",
            f"当前写作角度：{plan.angle}",
            f"原始关键词：{plan.keyword or '未填写，由系统主题库选择'}",
            f"目标读者：{plan.target_reader}",
            f"禁止重复的内容点：{plan.avoid_repeat_point or '不要复用其他草稿的小标题、核心观点和胡哥总结'}",
            "输出格式要求：标题、图片插入位、开头、分段正文、胡哥总结。",
            "公众号排版要求：1000字以内，短段落，强实用性，措辞幽默，引用公开数据源，给出门店今天能执行的动作。",
        ]
    )


def _hot_plans(keyword: str, count: int) -> list[TopicPlan]:
    plans = []
    for suffix, angle, avoid in HOT_SUBTOPICS[:count]:
        plans.append(
            TopicPlan(
                topic=f"{keyword}{suffix}",
                angle=angle,
                avoid_repeat_point=avoid,
                keyword=keyword,
            )
        )
    return plans


def _ten_lessons_plans(keyword: str, count: int, *, seed: int | None) -> list[TopicPlan]:
    topics = _pick_distinct(TEN_LESSONS_TOPICS, count, seed=seed)
    plans = []
    used_angles: set[str] = set()
    for index, topic_name in enumerate(topics):
        angle = _angle_for_topic(topic_name, index)
        angle = _unique_angle(angle, used_angles, index)
        used_angles.add(angle)
        topic = f"{topic_name}10句劝"
        if keyword:
            topic = f"{keyword}下的{topic}"
        plans.append(
            TopicPlan(
                topic=topic,
                angle=angle,
                avoid_repeat_point=f"不要写{_neighbor(topics, index)}",
                keyword=keyword,
            )
        )
    return plans


def _methodology_plans(keyword: str, count: int, *, seed: int | None) -> list[TopicPlan]:
    if keyword:
        base = [
            (f"{keyword}太乱怎么办", "菜单结构角度", "不要写客流下降"),
            (f"{keyword}不赚钱怎么办", "毛利角度", "不要写员工执行"),
            (f"{keyword}顾客不买单怎么办", "用户体验角度", "不要写成本控制"),
            (f"{keyword}执行不稳定怎么办", "门店执行角度", "不要写复购私域"),
            (f"{keyword}复购起不来怎么办", "复购角度", "不要写价格战"),
            (f"{keyword}客单价上不去怎么办", "客单价角度", "不要写加盟管控"),
            (f"{keyword}老板不会判断取舍怎么办", "老板决策角度", "不要写员工管理"),
            (f"{keyword}成本越控越乱怎么办", "成本控制角度", "不要写用户体验"),
            (f"{keyword}员工不会卖怎么办", "员工管理角度", "不要写品牌长期主义"),
            (f"{keyword}长期没有标准怎么办", "品牌长期主义角度", "不要写短期促销"),
        ]
        return [
            TopicPlan(topic=topic, angle=angle, avoid_repeat_point=avoid, keyword=keyword)
            for topic, angle, avoid in base[:count]
        ]

    topics = _pick_distinct(METHODOLOGY_TOPICS, count, seed=seed)
    plans = []
    used_angles: set[str] = set()
    for index, topic in enumerate(topics):
        angle = _angle_for_topic(topic, index)
        angle = _unique_angle(angle, used_angles, index)
        used_angles.add(angle)
        plans.append(
            TopicPlan(
                topic=topic,
                angle=angle,
                avoid_repeat_point=f"不要写{_neighbor(topics, index)}",
                keyword="",
            )
        )
    return plans


def _pick_distinct(values: list[str], count: int, *, seed: int | None) -> list[str]:
    rng = random.Random(seed)
    candidates = list(values)
    rng.shuffle(candidates)
    return candidates[:count]


def _neighbor(values: list[str], index: int) -> str:
    if len(values) <= 1:
        return "泛泛而谈的经营鸡汤"
    return values[(index + 1) % len(values)]


def _angle_for_topic(topic: str, index: int) -> str:
    if "成本" in topic or "损耗" in topic or "毛利" in topic:
        return "毛利角度"
    if "复购" in topic or "会员" in topic or "社群" in topic:
        return "复购角度"
    if "菜单" in topic or "新品" in topic or "定价" in topic:
        return "菜单结构角度"
    if "员工" in topic or "店长" in topic:
        return "员工管理角度"
    if "外卖" in topic or "客流" in topic:
        return "客流角度"
    if "加盟" in topic or "标准" in topic:
        return "加盟管控角度"
    if "卫生" in topic or "体验" in topic or "差评" in topic:
        return "用户体验角度"
    return WRITING_ANGLES[index % len(WRITING_ANGLES)]


def _unique_angle(angle: str, used_angles: set[str], index: int) -> str:
    if angle not in used_angles:
        return angle
    for offset in range(len(WRITING_ANGLES)):
        candidate = WRITING_ANGLES[(index + offset) % len(WRITING_ANGLES)]
        if candidate not in used_angles:
            return candidate
    return angle
