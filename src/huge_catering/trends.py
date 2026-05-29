from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import requests


TREND_QUERIES = [
    "餐饮 行业 热点",
    "餐饮 外卖 食品安全",
    "餐饮 消费 门店",
    "餐饮 老板 经营",
    "预制菜 外卖 茶饮 餐饮",
    "餐饮 社交媒体 热议",
    "餐饮 抖音 小红书 热点",
    "餐饮 微博 热搜",
    "茶饮 咖啡 火锅 外卖 热点",
    "美团 饿了么 京东 外卖 餐饮",
]

BING_NEWS_URL = "https://www.bing.com/news/search"
BING_WEB_URL = "https://www.bing.com/search"
BAIDU_URL = "https://www.baidu.com/s"
SOGOU_WEIXIN_URL = "https://weixin.sogou.com/weixin"
TOUTIAO_SEARCH_URL = "https://www.toutiao.com/search"

SOCIAL_SEARCH_QUERIES = [
    "site:weibo.com 餐饮 外卖 热点",
    "site:xiaohongshu.com 餐饮 外卖 茶饮",
    "site:douyin.com 餐饮 外卖 食品安全",
    "site:bilibili.com 餐饮 探店 外卖",
    "site:zhihu.com 餐饮 消费 门店",
    "site:mp.weixin.qq.com 餐饮 外卖 预制菜",
]

DOUYIN_HOT_URLS = [
    "https://www.douyin.com/hot",
    "https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/",
    "https://aweme.snssdk.com/aweme/v1/hot/search/list/",
]

STOPWORDS = {
    "餐饮",
    "行业",
    "新闻",
    "热点",
    "昨天",
    "今日",
    "中国",
    "市场",
    "企业",
    "公司",
    "门店",
    "老板",
    "一个",
    "如何",
    "为什么",
    "发布",
    "发展",
    "相关",
    "记者",
    "表示",
}

FALLBACK_KEYWORDS = ["外卖", "复购", "食品安全", "成本", "客单价"]

HOT_TERMS = [
    "外卖大战",
    "外卖",
    "消费者权益",
    "投诉",
    "白皮书",
    "食品安全",
    "餐饮报告",
    "餐饮产业",
    "炒菜机器人",
    "机器人",
    "连锁餐饮",
    "餐饮峰会",
    "江湖菜",
    "西贝",
    "预制菜",
    "茶饮",
    "加盟",
    "客单价",
    "复购",
    "成本",
    "AI营销",
    "情绪营销",
]


@dataclass(frozen=True)
class TrendSnapshot:
    target_date: date
    keywords: list[str]
    summary: str
    source_titles: list[str]
    keyword_counts: dict[str, int] | None = None


def trend_cache_path(output_dir: Path) -> Path:
    return output_dir.parent / "data" / "trend_cache.json"


def load_or_fetch_trends(*, output_dir: Path, publish_date: date) -> TrendSnapshot:
    target_date = publish_date - timedelta(days=1)
    cache_path = trend_cache_path(output_dir)
    cache = _read_cache(cache_path)
    key = target_date.isoformat()
    if key in cache:
        cached = _snapshot_from_cache(target_date, cache[key])
        if len(cached.keywords) >= 10 and cached.keyword_counts:
            return cached

    snapshot = fetch_yesterday_catering_trends(target_date=target_date)
    cache[key] = {
        "keywords": snapshot.keywords,
        "summary": snapshot.summary,
        "source_titles": snapshot.source_titles,
        "keyword_counts": snapshot.keyword_counts or {},
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def fetch_yesterday_catering_trends(*, target_date: date) -> TrendSnapshot:
    titles: list[str] = []
    for query in TREND_QUERIES:
        try:
            titles.extend(_bing_news_titles(query=query, target_date=target_date))
            titles.extend(_bing_web_titles(query=query))
            titles.extend(_baidu_titles(query=query))
            titles.extend(_sogou_weixin_titles(query=query))
            titles.extend(_toutiao_titles(query=query))
        except requests.RequestException:
            continue
        except ET.ParseError:
            continue
    for query in SOCIAL_SEARCH_QUERIES:
        try:
            titles.extend(_bing_web_titles(query=query))
        except requests.RequestException:
            continue
    titles.extend(_douyin_hot_titles())

    unique_titles = list(dict.fromkeys(title for title in titles if title.strip()))
    keyword_counts = extract_keyword_counts(unique_titles)
    keywords = [word for word, _ in keyword_counts.most_common(10)]
    if not keywords:
        keywords = FALLBACK_KEYWORDS
    summary = _build_summary(keywords, unique_titles)
    return TrendSnapshot(
        target_date=target_date,
        keywords=keywords[:10],
        summary=summary,
        source_titles=unique_titles[:30],
        keyword_counts=dict(keyword_counts.most_common(20)),
    )


def extract_keywords(titles: list[str]) -> list[str]:
    return [word for word, _ in extract_keyword_counts(titles).most_common(10)]


def extract_keyword_counts(titles: list[str]) -> Counter[str]:
    text = " ".join(titles)
    term_counter: Counter[str] = Counter()
    for term in HOT_TERMS:
        count = text.count(term)
        if count:
            term_counter[term] += count

    candidates = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,12}", text)
    counter: Counter[str] = Counter()
    for word in candidates:
        if word in STOPWORDS or len(word) < 2:
            continue
        if "年" in word or "月" in word:
            continue
        if len(word) > 6:
            continue
        if re.fullmatch(r"\d+", word):
            continue
        counter[word] += 1
    combined: Counter[str] = Counter()
    combined.update(term_counter)
    for word, count in counter.items():
        combined[word] += count
    preferred = Counter(
        {
            word: count
            for word, count in combined.items()
            if any(seed in word for seed in ["外卖", "食品", "安全", "成本", "茶饮", "预制", "消费", "门店", "价格", "复购", "服务", "加盟", "供应", "火锅", "咖啡", "奶茶", "美团", "饿了么", "京东", "探店"])
        }
    )
    if preferred:
        rest = Counter({word: count for word, count in combined.items() if word not in preferred})
        preferred.update({word: count for word, count in rest.most_common(10)})
        return preferred
    return combined


def snapshot_for_keyword(snapshot: TrendSnapshot, keyword: str) -> TrendSnapshot:
    keywords = [keyword] + [item for item in snapshot.keywords if item != keyword]
    count = (snapshot.keyword_counts or {}).get(keyword, 0)
    summary = (
        f"昨天公开信息源中，{keyword}在餐饮相关标题和摘要里引用频次靠前"
        f"{f'，统计引用约{count}次' if count else ''}。"
        "适合从客流、毛利、体验、复购和风险控制角度拆成门店动作。"
    )
    return replace(snapshot, keywords=keywords[:10], summary=summary)


def trend_topic_id(snapshot: TrendSnapshot) -> str:
    seed = "|".join(snapshot.keywords) + snapshot.target_date.isoformat()
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"trend_{snapshot.target_date.strftime('%Y%m%d')}_{digest}"


def title_base_from_trends(snapshot: TrendSnapshot) -> str:
    keyword = snapshot.keywords[0] if snapshot.keywords else "餐饮经营"
    templates = [
        f"昨天餐饮圈都在聊{keyword}，老板要听这10句劝",
        f"{keyword}又成热点，餐饮老板先别急着跟风",
        f"从{keyword}看餐饮赚钱，老板要抓住这10点",
        f"餐饮老板注意：{keyword}背后藏着10个经营信号",
    ]
    index = int(hashlib.sha1(keyword.encode("utf-8")).hexdigest()[:2], 16) % len(templates)
    return templates[index]


def _bing_news_titles(*, query: str, target_date: date) -> list[str]:
    response = requests.get(
        BING_NEWS_URL,
        params={"q": query, "FORM": "HDRSC6"},
        headers=_browser_headers(),
        timeout=20,
    )
    response.raise_for_status()
    if response.text.lstrip().startswith("<!doctype html") or "<html" in response.text[:500].lower():
        return _bing_html_titles(response.text)
    return _rss_titles(response.text, target_date=target_date)


def _rss_titles(xml_text: str, *, target_date: date) -> list[str]:
    root = ET.fromstring(xml_text)
    dated_titles: list[str] = []
    fallback_titles: list[str] = []
    for item in root.findall(".//item"):
        title = item.findtext("title") or ""
        if title:
            fallback_titles.append(_clean_title(title))
        pub_date = item.findtext("pubDate") or ""
        item_date = _parse_pub_date(pub_date)
        if item_date is None or abs((item_date - target_date).days) <= 2:
            dated_titles.append(_clean_title(title))
    return dated_titles or fallback_titles[:8]


def _bing_html_titles(html: str) -> list[str]:
    titles: list[str] = []
    for pattern in [
        r'<a[^>]+class="title"[^>]*>(.*?)</a>',
        r'<a[^>]+aria-label="([^"]{6,120})"',
        r'<h2[^>]*>\s*<a[^>]*>(.*?)</a>',
    ]:
        for match in re.findall(pattern, html, flags=re.I | re.S):
            title = _strip_html(match)
            if _looks_like_catering_title(title):
                titles.append(title)
    return list(dict.fromkeys(titles))[:12]


def _bing_web_titles(*, query: str) -> list[str]:
    response = requests.get(
        BING_WEB_URL,
        params={"q": query},
        headers=_browser_headers(),
        timeout=20,
    )
    response.raise_for_status()
    return _generic_html_titles(response.text)[:12]


def _baidu_titles(*, query: str) -> list[str]:
    response = requests.get(
        BAIDU_URL,
        params={"wd": query},
        headers=_browser_headers(),
        timeout=20,
    )
    response.raise_for_status()
    return _generic_html_titles(response.text)[:10]


def _sogou_weixin_titles(*, query: str) -> list[str]:
    response = requests.get(
        SOGOU_WEIXIN_URL,
        params={"type": "2", "query": query},
        headers=_browser_headers(),
        timeout=20,
    )
    response.raise_for_status()
    return _generic_html_titles(response.text)[:10]


def _toutiao_titles(*, query: str) -> list[str]:
    response = requests.get(
        TOUTIAO_SEARCH_URL,
        params={"keyword": query},
        headers=_browser_headers(),
        timeout=20,
    )
    response.raise_for_status()
    return _generic_html_titles(response.text)[:10]


def _generic_html_titles(html: str) -> list[str]:
    titles: list[str] = []
    for pattern in [
        r"<title[^>]*>(.*?)</title>",
        r"<h1[^>]*>(.*?)</h1>",
        r"<h2[^>]*>(.*?)</h2>",
        r"<h3[^>]*>(.*?)</h3>",
        r'"title"\s*:\s*"([^"]{4,120})"',
        r'"word"\s*:\s*"([^"]{2,60})"',
        r'"sentence"\s*:\s*"([^"]{2,80})"',
        r'aria-label="([^"]{4,120})"',
    ]:
        for match in re.findall(pattern, html, flags=re.I | re.S):
            title = _strip_html(_decode_json_text(match))
            if _looks_like_catering_title(title):
                titles.append(title)
    return list(dict.fromkeys(titles))


def _douyin_hot_titles() -> list[str]:
    titles: list[str] = []
    for url in DOUYIN_HOT_URLS:
        try:
            response = requests.get(url, headers=_browser_headers(), timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        titles.extend(_extract_douyin_titles(response.text))
        if len(titles) >= 20:
            break
    catering_titles = [title for title in titles if _looks_like_catering_title(title)]
    return list(dict.fromkeys(catering_titles))[:20]


def _extract_douyin_titles(text: str) -> list[str]:
    titles: list[str] = []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        titles.extend(_walk_json_for_titles(data))

    for pattern in [
        r'"word"\s*:\s*"([^"]{2,40})"',
        r'"sentence"\s*:\s*"([^"]{2,60})"',
        r'"title"\s*:\s*"([^"]{2,60})"',
        r'"desc"\s*:\s*"([^"]{2,60})"',
    ]:
        titles.extend(_decode_json_text(match) for match in re.findall(pattern, text))
    return [_clean_title(title) for title in titles if _valid_hot_title(title)]


def _walk_json_for_titles(value: object) -> list[str]:
    titles: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"word", "sentence", "title", "desc"} and isinstance(item, str):
                titles.append(item)
            else:
                titles.extend(_walk_json_for_titles(item))
    elif isinstance(value, list):
        for item in value:
            titles.extend(_walk_json_for_titles(item))
    return titles


def _parse_pub_date(value: str) -> date | None:
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError):
        return None


def _clean_title(title: str) -> str:
    title = re.sub(r"\s*-\s*[^-]{1,40}$", "", title).strip()
    return re.sub(r"\s+", " ", title)


def _strip_html(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return _clean_title(unescape(value))


def _decode_json_text(value: str) -> str:
    try:
        return bytes(value, "utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return value


def _valid_hot_title(title: str) -> bool:
    title = title.strip()
    return 2 <= len(title) <= 60 and not title.startswith(("http", "//"))


def _looks_like_catering_title(title: str) -> bool:
    return any(
        term in title
        for term in [
            "餐饮",
            "外卖",
            "食品",
            "茶饮",
            "预制菜",
            "火锅",
            "咖啡",
            "奶茶",
            "门店",
            "消费",
            "投诉",
            "美团",
            "饿了么",
            "京东",
            "西贝",
        ]
    )


def _browser_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
    }


def _build_summary(keywords: list[str], titles: list[str]) -> str:
    keyword_text = "、".join(keywords[:10])
    if titles:
        return f"昨天公开信息源中的餐饮相关讨论集中在{keyword_text}，适合从成本、体验、复购和风险控制角度拆解。"
    return f"未抓到稳定新闻源，今日按{keyword_text}这些餐饮经营关键词生成稳妥选题。"


def _read_cache(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


def _snapshot_from_cache(target_date: date, raw: dict[str, object]) -> TrendSnapshot:
    return TrendSnapshot(
        target_date=target_date,
        keywords=[str(item) for item in raw.get("keywords", FALLBACK_KEYWORDS)],
        summary=str(raw.get("summary", "")),
        source_titles=[str(item) for item in raw.get("source_titles", [])],
        keyword_counts={
            str(key): int(value)
            for key, value in (raw.get("keyword_counts", {}) if isinstance(raw.get("keyword_counts"), dict) else {}).items()
            if isinstance(value, int)
        },
    )
