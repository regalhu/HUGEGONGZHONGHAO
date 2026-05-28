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
) -> Topic:
    keywords = keyword_override or snapshot.keywords or ["餐饮经营"]
    primary = keywords[0]
    secondary = keywords[1] if len(keywords) > 1 else "复购"
    title = _title_from_style(primary, title_style, snapshot)
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


def _title_from_style(primary: str, title_style: str, snapshot: TrendSnapshot) -> str:
    if title_style == "ten_lessons":
        return f"餐饮老板想赚钱，先把{primary}这10件事想明白"
    if title_style == "data_signal":
        return f"餐饮老板注意：{primary}背后藏着10个经营信号"
    if title_style == "question_hook":
        return f"{primary}为什么突然火了？餐饮老板要看这10点"
    return title_base_from_trends(snapshot)


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
