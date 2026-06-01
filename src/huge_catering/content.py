from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import random
from typing import Any

from .history import HistoryEntry, recently_used_topic_ids, used_topic_for_date
from .models import Advice, Article
from .trends import TrendSnapshot, title_base_from_trends, trend_topic_id


@dataclass(frozen=True)
class Topic:
    id: str
    name: str
    title: str
    digest: str
    intro: str
    advices: list[Advice]
    trend_keywords: list[str] | None = None
    trend_summary: str = ""
    trend_sources: list[str] | None = None


def load_topics(path: Path) -> list[Topic]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    topics: list[Topic] = []
    for item in raw:
        advices = [
            Advice(index=index, title=str(advice[0]), body=str(advice[1]))
            for index, advice in enumerate(item["advices"], start=1)
        ]
        topics.append(
            Topic(
                id=str(item["id"]),
                name=str(item["name"]),
                title=str(item["title"]),
                digest=str(item["digest"]),
                intro=str(item["intro"]),
                advices=advices,
                trend_keywords=[
                    str(keyword) for keyword in item.get("trend_keywords", [])
                ]
                if isinstance(item.get("trend_keywords"), list)
                else None,
                trend_summary=str(item.get("trend_summary", "")),
                trend_sources=[str(source) for source in item.get("trend_sources", [])]
                if isinstance(item.get("trend_sources"), list)
                else None,
            )
        )
    if not topics:
        raise ValueError(f"No topics found in {path}")
    return topics


def topics_from_raw(raw_topics: list[dict[str, object]]) -> list[Topic]:
    topics: list[Topic] = []
    for item in raw_topics:
        raw_advices = item.get("advices")
        if not isinstance(raw_advices, list):
            continue
        advices = [
            Advice(index=index, title=str(advice[0]), body=str(advice[1]))
            for index, advice in enumerate(raw_advices, start=1)
            if isinstance(advice, (list, tuple)) and len(advice) >= 2
        ]
        if len(advices) != 10:
            continue
        topics.append(
            Topic(
                id=str(item["id"]),
                name=str(item["name"]),
                title=str(item["title"]),
                digest=str(item["digest"]),
                intro=str(item["intro"]),
                advices=advices,
            )
        )
    if not topics:
        raise ValueError("No valid topics were generated")
    return topics


def choose_topic(
    topics: list[Topic],
    *,
    publish_date: date,
    history: list[HistoryEntry],
    seed: int | None = None,
) -> Topic:
    topic_by_id = {topic.id: topic for topic in topics}
    existing_topic_id = used_topic_for_date(history, publish_date)
    if existing_topic_id and existing_topic_id in topic_by_id:
        return topic_by_id[existing_topic_id]

    used_ids = recently_used_topic_ids(history)
    candidates = [topic for topic in topics if topic.id not in used_ids]
    if not candidates:
        candidates = topics

    rng = random.Random(seed if seed is not None else int(publish_date.strftime("%Y%m%d")))
    return rng.choice(candidates)


def generate_article(
    *,
    brand_name: str,
    author_name: str,
    publish_date: date,
    topic: Topic,
    issue_number: int,
    article_type: str = "ten_lessons",
) -> Article:
    topic = _topic_for_article_type(topic, article_type=article_type, issue_number=issue_number)
    title = _article_title(topic=topic, issue_number=issue_number, article_type=article_type)
    conclusion = _conclusion(author_name=author_name, brand_name=brand_name, article_type=article_type)
    return Article(
        title=title,
        digest=topic.digest,
        author=author_name,
        publish_date=publish_date,
        topic_id=topic.id,
        topic_name=topic.name,
        issue_number=issue_number,
        intro=topic.intro,
        advices=topic.advices,
        conclusion=conclusion,
        article_type=article_type,
        trend_keywords=topic.trend_keywords or [],
        trend_summary=topic.trend_summary,
        trend_sources=topic.trend_sources or [],
        tags=["餐饮经营", topic.name, "老板复盘"],
    )


def topic_from_trends(
    snapshot: TrendSnapshot,
    *,
    article_type: str = "hot_interpretation",
    keyword_override: list[str] | None = None,
    title_variant: int | None = None,
) -> Topic:
    keywords = keyword_override or snapshot.keywords or ["餐饮经营"]
    primary = keywords[0]
    secondary = keywords[1] if len(keywords) > 1 else "复购"
    tertiary = keywords[2] if len(keywords) > 2 else "门店动作"
    title = _title_from_style(
        primary,
        secondary,
        tertiary,
        article_type,
        snapshot,
        title_variant=title_variant,
    )
    digest = _digest_for_type(article_type, primary, secondary)
    intro = _intro_for_type(article_type, primary, secondary)
    advices = _advices_for_type(article_type=article_type, primary=primary, secondary=secondary, tertiary=tertiary, keywords=keywords)
    return Topic(
        id=trend_topic_id(snapshot),
        name=f"热点：{primary}",
        title=title,
        digest=digest,
        intro=intro,
        advices=advices,
        trend_keywords=keywords,
        trend_summary=snapshot.summary,
        trend_sources=snapshot.source_titles[:5],
    )


def _title_from_style(
    primary: str,
    secondary: str,
    tertiary: str,
    article_type: str,
    snapshot: TrendSnapshot,
    *,
    title_variant: int | None = None,
) -> str:
    if title_variant is None:
        return _single_title_from_style(primary, article_type, snapshot)

    templates = _title_templates(primary, secondary, tertiary, article_type)
    return templates[title_variant % len(templates)]


def _single_title_from_style(primary: str, article_type: str, snapshot: TrendSnapshot) -> str:
    if article_type == "methodology":
        return f"小店{primary}越做越乱？先用这3步把利润拉回来"
    if article_type == "ten_lessons":
        return "餐饮要赚钱 听我10句劝"
    return title_base_from_trends(snapshot)


def _title_templates(primary: str, secondary: str, tertiary: str, article_type: str) -> list[str]:
    if article_type == "ten_lessons":
        return [
            "餐饮要赚钱 听我10句劝",
        ]
    if article_type == "methodology":
        return [
            f"小店{primary}越做越乱？先用这3步把利润拉回来",
            f"{secondary}上不去？老板先把这张检查清单跑一遍",
            f"门店利润总漏水？从{tertiary}开始做这4步",
            f"别再凭感觉管店，{primary}要先拆成这3个动作",
            f"生意不差却不赚钱？用这套方法先查{secondary}",
            f"小店想稳住利润，别先加菜，先改{primary}",
            f"{tertiary}越忙越乱？餐饮老板先用这份流程表",
            f"复购起不来？别急着打折，先按3步重做{primary}",
            f"员工执行总走样？把{secondary}拆成这张清单",
            f"餐饮小店想少亏钱，先把{primary}这件事做细",
        ]
    return [
        f"{primary}又热了，餐饮店到底该改哪里？",
        f"{primary}不是热闹，餐饮老板要先算这几笔账",
        f"{primary}冲上来，门店别急跟风，先看这3个风险",
        f"最近都在聊{primary}，餐饮店赚钱点可能不在表面",
        f"{secondary}变了，餐饮老板今天要改哪3个动作？",
        f"{primary}看着很火，为什么有的店越跟越亏？",
        f"餐饮老板注意：{primary}背后藏着客流和毛利变化",
        f"{primary}来了，门店先别卷价格，先改体验",
        f"本周{primary}升温，小店要防这3个坑",
        f"{primary}带来的不是风口，是餐饮老板的一次体检",
    ]


def _article_title(*, topic: Topic, issue_number: int, article_type: str) -> str:
    if article_type == "ten_lessons":
        return f"餐饮要赚钱 听我10句劝｜第{issue_number}期"
    return topic.title


def _advices_for_type(*, article_type: str, primary: str, secondary: str, tertiary: str, keywords: list[str]) -> list[Advice]:
    if article_type == "methodology":
        return _methodology_sections(primary=primary, secondary=secondary, tertiary=tertiary)
    if article_type == "hot_interpretation":
        return _hot_interpretation_sections(primary=primary, secondary=secondary, keywords=keywords)
    return _ten_lessons_advices(primary=primary, secondary=secondary, keywords=keywords)


def _ten_lessons_advices(*, primary: str, secondary: str, keywords: list[str]) -> list[Advice]:
    joined = "、".join(keywords[:5])
    rows = [
        ("少上新，多算账", f"新菜不是越多越赚钱。先看毛利、出餐、复购，别让菜单比老板还累。"),
        ("客流贵，复购香", f"拉新像请客，复购像收租。今天先把老客二次到店的理由写清楚。"),
        ("菜单乱，利润散", f"围绕{primary}，只留能卖、能赚、能快出的菜。菜单瘦一点，利润反而胖一点。"),
        ("便宜能来人，体验能留人", f"打折只能让顾客进门，服务和出品才让顾客回头。别把优惠当止痛药。"),
        ("员工不会说，老板白忙活", f"把主推菜、活动、安心点写成一句话术。员工说得清，顾客才买得明白。"),
        ("后厨稳，前厅才敢喊", f"克重、出餐、卫生不稳，营销越猛翻车越快。先稳后厨，再放大声音。"),
        ("别盯热闹，要盯数字", f"围绕{joined}，每天看差评、退款、出餐时长、复购率。数字难听，但比感觉靠谱。"),
        ("小改先试，大改慢来", f"新套餐、新话术先小范围测。老客点头了，再全店铺开，别一上来就豪赌。"),
        ("老板别只救火，要做流程", f"今天发现的问题，明天要变成检查表。靠人盯会累死，靠流程才省命。"),
        ("活得久，才有钱赚", f"餐饮不是百米冲刺，是天天跑小步。少踩坑、稳复购，店才有明天。"),
    ]
    return [Advice(index=index, title=title, body=body) for index, (title, body) in enumerate(rows, start=1)]


def _hot_interpretation_sections(*, primary: str, secondary: str, keywords: list[str]) -> list[Advice]:
    return [
        Advice(1, "这个热点为什么和餐饮老板有关", f"{primary}表面是话题，背后是顾客选择变了。顾客在意价格、速度、安心感，餐饮店就不能只看热搜，要看它会不会影响进店理由。"),
        Advice(2, "它影响哪几笔钱", f"先拆五笔账：客流会不会被带动，客单会不会被压低，毛利会不会被吃掉，复购会不会变强，风险会不会放大。{secondary}如果也在升温，说明顾客不是随便聊聊。"),
        Advice(3, "门店今天能做的3个动作", "第一，改一句前厅话术，让员工讲清楚你家优势。第二，调一个菜单推荐位，把高毛利产品放到顾客眼前。第三，查一次差评和退款，别让小问题借热点变大事故。"),
        Advice(4, "胡哥提醒", f"热点不是让老板追着跑，是让老板回头看店。今天能落地一个动作，比转发十条{primary}更值钱。"),
    ]


def _methodology_sections(*, primary: str, secondary: str, tertiary: str) -> list[Advice]:
    return [
        Advice(1, "问题为什么发生", f"很多店不是不会卖，而是{primary}没标准：菜单想加就加，活动想做就做，员工靠感觉执行。结果越忙越乱，利润偷偷漏。"),
        Advice(2, "老板常见误区", "第一，觉得菜越多越能满足顾客。第二，觉得打折能解决复购。第三，觉得员工不执行就是态度差。其实多数问题，是标准没写清、检查没跟上。"),
        Advice(3, "可执行方法：3步先落地", f"第一步，列出销量前10和毛利前10，找出真正赚钱的菜。第二步，把{secondary}相关动作写成一句话术和一张检查表。第三步，每晚复盘3个数：客单、毛利、复购。"),
        Advice(4, "检查清单", f"今天就查：菜单有没有主推，员工会不会讲，出餐是否稳定，差评有没有归类，{tertiary}有没有负责人。五项过三项，店就能往前走。"),
        Advice(5, "胡哥总结", "方法论不是挂墙上的口号，是每天能照着做的动作。餐饮老板少一点凭感觉，多一点检查表，利润就不会天天失踪。"),
    ]


def _topic_for_article_type(topic: Topic, *, article_type: str, issue_number: int) -> Topic:
    keywords = topic.trend_keywords or [topic.name, "复购", "门店利润"]
    primary = keywords[0] if keywords else topic.name
    secondary = keywords[1] if len(keywords) > 1 else "复购"
    tertiary = keywords[2] if len(keywords) > 2 else "菜单"
    if article_type == "ten_lessons":
        return Topic(
            id=topic.id,
            name=topic.name,
            title=f"餐饮要赚钱 听我10句劝｜第{issue_number}期",
            digest="10句短劝，帮餐饮老板把利润、复购、菜单和执行重新捋顺。",
            intro=f"本期主题：围绕{primary}，聊餐饮老板今天就能用的10句劝。",
            advices=_ten_lessons_advices(primary=primary, secondary=secondary, keywords=keywords),
            trend_keywords=keywords,
            trend_summary=topic.trend_summary,
            trend_sources=topic.trend_sources,
        )
    if article_type == "methodology":
        return Topic(
            id=topic.id,
            name=topic.name,
            title=_title_templates(primary, secondary, tertiary, "methodology")[issue_number % 10],
            digest=f"围绕{primary}，给餐饮老板一套能落地的经营方法。",
            intro=f"开店最怕不是没想法，是想法太多、动作太乱。今天就拿{primary}这个痛点，拆成一套能执行的方法。",
            advices=_methodology_sections(primary=primary, secondary=secondary, tertiary=tertiary),
            trend_keywords=keywords,
            trend_summary=topic.trend_summary,
            trend_sources=topic.trend_sources,
        )
    return Topic(
        id=topic.id,
        name=topic.name,
        title=_title_templates(primary, secondary, tertiary, "hot_interpretation")[issue_number % 10],
        digest=f"从{primary}切入，帮餐饮老板看清客流、客单、毛利、复购和风险。",
        intro=f"最近{primary}又被聊起来了。别急着跟风，胡哥先帮你把热闹翻译成门店能做的事。",
        advices=_hot_interpretation_sections(primary=primary, secondary=secondary, keywords=keywords),
        trend_keywords=keywords,
        trend_summary=topic.trend_summary,
        trend_sources=topic.trend_sources,
    )


def _digest_for_type(article_type: str, primary: str, secondary: str) -> str:
    if article_type == "methodology":
        return f"围绕{primary}这个经营问题，拆出餐饮门店能直接执行的方法和检查清单。"
    if article_type == "hot_interpretation":
        return f"从{primary}热点切入，拆清它对客流、客单、毛利、复购和风险的影响。"
    return f"胡哥围绕{primary}、{secondary}，给餐饮老板10句短、狠、能执行的劝。"


def _intro_for_type(article_type: str, primary: str, secondary: str) -> str:
    if article_type == "methodology":
        return f"小店最怕{primary}越做越乱：老板忙、员工乱、利润薄。今天不讲玄学，只拆能落地的步骤。"
    if article_type == "hot_interpretation":
        return f"最近{primary}又热了。餐饮老板别只看热闹，先看它会不会影响顾客进店、点单和复购。"
    return f"本期主题：围绕{primary}和{secondary}，聊餐饮老板今天就能用的10句劝。"


def _conclusion(*, author_name: str, brand_name: str, article_type: str) -> str:
    if article_type == "methodology":
        return f"{author_name}总结：方法不是越复杂越厉害，能每天照着做才值钱。关注「{brand_name}」，咱们继续把小店利润一点点抠回来。"
    if article_type == "hot_interpretation":
        return f"{author_name}总结：热点会过去，动作要留下。今天先改一个菜单、一个话术、一个检查项，别让流量白白路过。"
    return f"{author_name}总结：餐饮赚钱没有神招，都是笨功夫。少一点拍脑袋，多一点算账和复盘，店就能活得久、赚得稳。"


def default_topic_library_path() -> Path:
    return Path("data") / "topic_library.json"
