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
) -> Article:
    title = f"{topic.title}｜{issue_number}"
    conclusion = (
        f"我是{author_name}，每天陪餐饮老板把账算清、把店管顺。"
        f"关注「{brand_name}」，咱们一天解决一个真问题。"
    )
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
        trend_keywords=topic.trend_keywords or [],
        trend_summary=topic.trend_summary,
        tags=["餐饮经营", topic.name, "老板复盘"],
    )


def topic_from_trends(
    snapshot: TrendSnapshot,
    *,
    title_style: str = "hot_warning",
    article_angle: str = "",
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
        title_style,
        snapshot,
        title_variant=title_variant,
    )
    digest = f"胡哥根据昨天餐饮热点关键词{primary}、{secondary}，拆成今天老板能用的10句经营提醒。"
    angle_sentence = f"这篇重点按「{article_angle}」来拆。" if article_angle else ""
    intro = (
        f"老板，昨天餐饮相关内容里，{primary}这个词出现得很扎眼。"
        f"热点不是拿来凑热闹的，是拿来反推门店经营的。{angle_sentence}"
        f"今天这10句，咱们就从{primary}说到{secondary}，看看哪些动作今天就能改。"
    )
    advices = _trend_advices(primary=primary, secondary=secondary, keywords=keywords, article_angle=article_angle)
    return Topic(
        id=trend_topic_id(snapshot),
        name=f"热点：{primary}",
        title=title,
        digest=digest,
        intro=intro,
        advices=advices,
        trend_keywords=keywords,
        trend_summary=snapshot.summary,
    )


def _title_from_style(
    primary: str,
    secondary: str,
    tertiary: str,
    title_style: str,
    snapshot: TrendSnapshot,
    *,
    title_variant: int | None = None,
) -> str:
    if title_variant is None:
        return _single_title_from_style(primary, title_style, snapshot)

    templates = _title_templates(primary, secondary, tertiary, title_style)
    return templates[title_variant % len(templates)]


def _single_title_from_style(primary: str, title_style: str, snapshot: TrendSnapshot) -> str:
    if title_style == "ten_lessons":
        return f"餐饮老板想赚钱，先把{primary}这10件事想明白"
    if title_style == "data_signal":
        return f"餐饮老板注意：{primary}背后藏着10个经营信号"
    if title_style == "question_hook":
        return f"{primary}为什么突然火了？餐饮老板要看这10点"
    return title_base_from_trends(snapshot)


def _title_templates(primary: str, secondary: str, tertiary: str, title_style: str) -> list[str]:
    if title_style == "ten_lessons":
        return [
            f"餐饮老板想赚钱，先把{primary}这10件事想明白",
            f"别只盯{primary}热度，真正赚钱靠这10个动作",
            f"从{primary}到{secondary}，餐饮老板今天要听10句劝",
            f"餐饮赚钱不是撞运气，{primary}背后有10个提醒",
            f"{primary}热起来以后，老板先把这10笔账算清",
            f"门店想多赚一点，先用10句话看懂{primary}",
            f"{secondary}变了，餐饮老板要记住这10句实话",
            f"别让{primary}白白过去，今天就改这10件小事",
            f"餐饮老板别急着跟风，先听胡哥这10句劝",
            f"围绕{primary}赚钱，老板要先避开这10个坑",
        ]
    if title_style == "data_signal":
        return [
            f"餐饮老板注意：{primary}背后藏着10个经营信号",
            f"{primary}升温，门店这10个数据要马上看",
            f"从{secondary}看餐饮生意，老板别忽略10个信号",
            f"{primary}不是热闹，是门店经营的10个提醒",
            f"顾客在讨论{primary}，老板要盯住这10个变化",
            f"{tertiary}正在变化，餐饮老板要抓10个信号",
            f"今天餐饮热点里，最该复盘的是这10个数据",
            f"{primary}背后，藏着餐饮门店的10个赚钱信号",
            f"老板别只看客流，{secondary}才是这10个信号的关键",
            f"餐饮经营要变快，先读懂{primary}这10个信号",
        ]
    if title_style == "question_hook":
        return [
            f"{primary}为什么突然火了？餐饮老板要看这10点",
            f"{primary}到底跟你门店有什么关系？胡哥讲10句",
            f"顾客为什么在意{primary}？餐饮老板先想10个问题",
            f"{secondary}变热，老板到底该不该跟？先看这10点",
            f"{primary}会影响生意吗？餐饮老板先查这10件事",
            f"为什么同样蹭{primary}，有的店赚钱有的店亏？",
            f"{tertiary}来了，餐饮老板今天该怎么判断？",
            f"{primary}热度过后，门店还能留下什么？",
            f"老板要不要追{primary}？先把这10个问题问清楚",
            f"{secondary}被讨论，餐饮店到底该改哪里？",
        ]
    return [
        f"昨天餐饮圈都在聊{primary}，老板要听这10句劝",
        f"{primary}又成热点，餐饮老板先别急着跟风",
        f"从{primary}看餐饮赚钱，老板要抓住这10点",
        f"餐饮老板注意：{primary}背后藏着10个经营信号",
        f"{primary}热起来以后，门店今天先改这3件事",
        f"别只看{primary}热闹，餐饮老板要看懂生意变化",
        f"{secondary}也在变，老板别错过这10个经营提醒",
        f"昨天热点指向{primary}，今天门店要先做复盘",
        f"从{primary}到{tertiary}，餐饮老板要少踩这些坑",
        f"餐饮老板别急，{primary}这波热度要这样用",
    ]


def _trend_advices(*, primary: str, secondary: str, keywords: list[str], article_angle: str = "") -> list[Advice]:
    joined = "、".join(keywords[:5])
    angle = article_angle or "门店今天能执行的动作"
    rows = [
        ("热点先别急着跟风", f"{primary}能上热度，说明顾客和市场都在关注。但老板先别急着学表面，先看它和你店里的产品、客群、价格带有没有关系。"),
        ("先问它影响哪笔钱", f"任何热点都要落到账上：会影响客流、客单、毛利，还是复购？今天先按{angle}来判断，说不清影响哪笔钱，就先不要乱投入。"),
        ("顾客关心的是具体体验", f"{primary}背后通常不是一个概念，而是顾客对安全、价格、速度、服务的感受。门店要把感受做出来。"),
        ("菜单要跟着需求微调", f"如果{secondary}也在被讨论，就说明顾客选择正在变。菜单不一定大改，但推荐位、套餐和文案要及时调。"),
        ("前厅话术要会解释", f"热点来了，顾客可能会问。员工不能只说不知道，要能用一句简单话讲清楚店里怎么做、为什么放心。"),
        ("后厨标准要经得起看", f"越是热点期，越要把克重、出品、卫生、包装做稳。热点会放大优点，也会放大小毛病。"),
        ("别让优惠掩盖问题", f"如果产品和体验没跟上，靠打折蹭{primary}只会吸来一次性顾客。优惠能拉新，复购还得靠基本功。"),
        ("每天看一个相关数据", f"围绕{joined}，老板至少盯一个数字：差评、复购、退款、出餐时间或毛利。数据会告诉你该改哪里。"),
        ("把热点变成店内动作", f"今天别只转发热点，落一个动作：改一句话术、查一次卫生、调一个套餐、复盘一道菜。能执行才有价值。"),
        ("热度会过去，能力要留下", f"{primary}这阵风迟早会过去，但你留下的标准、流程和顾客信任，会继续帮店赚钱。")
    ]
    return [Advice(index=index, title=title, body=body) for index, (title, body) in enumerate(rows, start=1)]


def default_topic_library_path() -> Path:
    return Path("data") / "topic_library.json"
