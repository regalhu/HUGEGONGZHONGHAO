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
    title = _article_title(topic=topic, issue_number=issue_number, article_type=article_type)
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
    digest = f"胡哥根据近5天餐饮高频关键词{primary}、{secondary}，拆成今天老板能用的10句经营提醒。"
    intro = (
        f"老板，公开平台这几天反复提到{primary}、{secondary}。"
        f"热闹咱不硬蹭，先把它翻译成门店今天能做的动作。"
    )
    advices = _trend_advices(primary=primary, secondary=secondary, keywords=keywords)
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
        return f"【本周】#{primary}#餐饮老板别乱学，先搭这套赚钱方法"
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
            f"【本周】#{primary}#餐饮老板别乱学，先搭这套赚钱方法",
            f"【今日】#{primary}#不是玄学，门店赚钱要按这套顺序来",
            f"【本周】#{secondary}#餐饮老板想稳住利润，先用这套方法论",
            f"【今日】#{primary}#胡哥讲透：小店也能执行的10个动作",
            f"【本周】#{tertiary}#别再凭感觉开店，这套复盘方法更管用",
            f"【今日】#{primary}#餐饮老板照着改，少走一半弯路",
            f"【本周】#{secondary}#门店经营别蛮干，先抓这10个关键点",
            f"【今日】#{primary}#老板最该补上的不是流量，是经营系统",
            f"【本周】#{tertiary}#餐饮赚钱的底层逻辑，胡哥拆成10句话",
            f"【今日】#{primary}#别急着跟风，先把方法用对",
        ]
    return [
        f"【今日】#{primary}#餐饮老板先别跟风，里面藏着赚钱信号",
        f"【今日】#{primary}#又冲上热度，门店今天要改哪3件事？",
        f"【本周】#{primary}#餐饮圈都在聊，真正该看的是这10点",
        f"【今日】#{secondary}#别只看热闹，老板要看懂顾客为什么买",
        f"【本周】#{primary}#这波热点背后，餐饮店最怕踩这几个坑",
        f"【今日】#{tertiary}#胡哥提醒：热点来了，先算清这笔账",
        f"【本周】#{primary}#为什么有的店跟风赚钱，有的店越跟越亏？",
        f"【今日】#{secondary}#餐饮老板要醒醒，机会不在表面",
        f"【本周】#{primary}#门店能不能接住热点，就看这10个动作",
        f"【今日】#{primary}#别让流量白来，老板先做这份复盘",
    ]


def _article_title(*, topic: Topic, issue_number: int, article_type: str) -> str:
    if article_type == "ten_lessons":
        return f"餐饮要赚钱 听我10句劝｜第{issue_number}期"
    return topic.title


def _trend_advices(*, primary: str, secondary: str, keywords: list[str]) -> list[Advice]:
    joined = "、".join(keywords[:5])
    rows = [
        ("先别激动，先对账", f"{primary}火了，不等于你该冲。先看它影响客流、毛利还是复购，别把热闹当利润。"),
        ("菜单只改一个点", f"围绕{secondary}，先调推荐位、套餐名或一句卖点。小改能测，大改容易把后厨改哭。"),
        ("员工要会一句话解释", f"顾客问起热点，前厅别装网速慢。准备一句人话：我们怎么做、为什么放心。"),
        ("后厨标准别掉链子", f"越有热度，越要稳克重、卫生、出餐。热点会放大优点，也会放大小毛病。"),
        ("优惠别当止痛药", f"产品没站稳，打折只是给问题加扩音器。先把体验补上，再谈拉新。"),
        ("每天盯一个数字", f"围绕{joined}，盯差评、退款、复购或出餐时长。数据不会哄老板开心，但会救老板钱包。"),
        ("短视频别只喊口号", f"拍一个真实动作：备料、出餐、检查、顾客反馈。真实比空话更像生意。"),
        ("老客先试，不急全店铺", f"新动作先给老客、小范围测。老客都不买账，别急着全网广播。"),
        ("把热点写进SOP", f"能留下来的不是热搜，是流程。把今天有效的话术、菜单和检查项写下来。"),
        ("热度过去，能力留下", f"{primary}会降温，但标准、复盘和信任会留在店里。餐饮赚钱，靠的就是这些慢功夫。")
    ]
    return [Advice(index=index, title=title, body=body) for index, (title, body) in enumerate(rows, start=1)]


def default_topic_library_path() -> Path:
    return Path("data") / "topic_library.json"
