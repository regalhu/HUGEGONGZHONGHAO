from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
import json
import re
import time
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
import xml.etree.ElementTree as ET

import requests


SEARCH_TIMEOUT_SECONDS = 6
FETCH_TIMEOUT_SECONDS = 6
MAX_FETCH_BYTES = 700_000
MAX_SUMMARY_CHARS = 180
MAX_QUOTE_CHARS = 42

BING_NEWS_RSS_URL = "https://www.bing.com/news/search"
BING_WEB_URL = "https://www.bing.com/search"
GOOGLE_NEWS_RSS_URL = "https://news.google.com/rss/search"

BLOCKED_HOST_KEYWORDS = {
    "douyin.com",
    "iesdouyin.com",
    "xiaohongshu.com",
    "news.google.com",
}

REFERENCE_QUERIES = {
    "owner": ["{keyword} 餐饮 利润 毛利 现金流", "{keyword} 外卖 团购 小店 经营"],
    "manager": ["{keyword} 餐饮 门店 出餐 差评 服务", "{keyword} 门店 店长 爆单 排班"],
    "operations": ["{keyword} 餐饮 连锁 标准化 加盟 管控", "{keyword} 餐饮 营运 督导 数据复盘"],
    "marketing": ["{keyword} 餐饮 流量 爆品 团购 会员", "{keyword} 抖音 小红书 餐饮 营销"],
    "supply": ["{keyword} 餐饮 供应链 采购 损耗 成本", "{keyword} 食材 成本 波动 餐饮"],
    "customer": ["{keyword} 餐饮 顾客 体验 价格 复购", "{keyword} 用户 评价 口味 服务"],
    "investor": ["{keyword} 餐饮 商业模式 坪效 人效", "{keyword} 餐饮 投资 回本周期 扩张"],
}

KEYWORD_CANDIDATES = [
    "低价",
    "补贴",
    "外卖",
    "团购",
    "毛利",
    "现金流",
    "复购",
    "差评",
    "出餐",
    "爆单",
    "门店",
    "加盟",
    "标准化",
    "供应链",
    "采购",
    "损耗",
    "食材",
    "会员",
    "私域",
    "抖音",
    "小红书",
    "坪效",
    "人效",
    "回本",
    "风险",
]


@dataclass(frozen=True)
class ReferenceArticle:
    source: str
    title: str
    url: str
    summary: str
    published_at: str = ""
    keywords: list[str] | None = None
    reference_point: str = ""
    short_quote: str = ""
    incomplete: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["keywords"] = self.keywords or []
        return data


@dataclass(frozen=True)
class ReferenceSearchResult:
    keyword: str
    role: str
    articles: list[ReferenceArticle]
    high_frequency_points: list[str]
    searched_queries: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "keyword": self.keyword,
            "role": self.role,
            "articles": [article.to_dict() for article in self.articles],
            "high_frequency_points": self.high_frequency_points,
            "searched_queries": self.searched_queries,
            "warnings": self.warnings,
        }


def search_reference_articles(
    *,
    keyword: str,
    role: str = "owner",
    limit: int = 6,
    cache_dir: Path | None = None,
    force_refresh: bool = False,
) -> ReferenceSearchResult:
    keyword = keyword.strip()
    if not keyword:
        raise ValueError("keyword is required")
    limit = max(1, min(limit, 10))
    role = role if role in REFERENCE_QUERIES else "owner"
    cache_path = _cache_path(cache_dir, keyword=keyword, role=role, limit=limit)
    if cache_path and cache_path.exists() and not force_refresh:
        cached = _read_cached(cache_path)
        if cached:
            return cached

    queries = [item.format(keyword=keyword) for item in REFERENCE_QUERIES[role]]
    queries.extend([
        f"site:mp.weixin.qq.com {keyword} 餐饮",
        f"{keyword} 餐饮 行业媒体",
    ])

    warnings: list[str] = []
    candidates: list[ReferenceArticle] = []
    for query in queries[:4]:
        try:
            candidates.extend(_bing_news_rss(query))
        except (requests.RequestException, ET.ParseError) as exc:
            warnings.append(f"Bing News RSS 查询失败：{query}，{exc}")
        try:
            candidates.extend(_google_news_rss(query))
        except (requests.RequestException, ET.ParseError) as exc:
            warnings.append(f"Google News RSS 查询失败：{query}，{exc}")
        try:
            candidates.extend(_bing_web_results(query))
        except requests.RequestException as exc:
            warnings.append(f"Bing Web 查询失败：{query}，{exc}")

    unique = _dedupe_articles(candidates)
    enriched: list[ReferenceArticle] = []
    for candidate in unique:
        if len(enriched) >= limit:
            break
        enriched.append(_enrich_article(candidate))

    points = _high_frequency_points(enriched)
    if not enriched:
        warnings.append("没有检索到可稳定抓取的公开网页；请使用手动粘贴参考资料。")

    result = ReferenceSearchResult(
        keyword=keyword,
        role=role,
        articles=enriched[:limit],
        high_frequency_points=points,
        searched_queries=queries[:4],
        warnings=warnings,
    )
    if cache_path:
        _write_cached(cache_path, result)
    return result


def format_references_for_prompt(articles: list[ReferenceArticle]) -> str:
    if not articles:
        return ""
    blocks = []
    for article in articles:
        blocks.append(
            "\n".join(
                [
                    f"标题：{article.title}",
                    f"来源：{article.source}",
                    f"链接：{article.url}",
                    f"发布时间：{article.published_at or '未标明'}",
                    f"摘要/观点：{article.summary}",
                    f"参考点：{article.reference_point or article.summary}",
                    "该来源仅用于话题参考，不作为数据依据。" if article.incomplete else "",
                ]
            ).strip()
        )
    return "\n\n".join(blocks)


def _bing_news_rss(query: str) -> list[ReferenceArticle]:
    response = requests.get(
        BING_NEWS_RSS_URL,
        params={"q": query, "format": "rss", "cc": "cn"},
        headers=_headers(),
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    articles: list[ReferenceArticle] = []
    for item in root.findall(".//item"):
        title = _xml_text(item, "title")
        url = _clean_url(_xml_text(item, "link"))
        summary = _clean_text(_xml_text(item, "description"))
        published_at = _format_pub_date(_xml_text(item, "pubDate"))
        source = _source_from_url(url) or "Bing News"
        if title and url and not _is_generic_title(title):
            articles.append(
                ReferenceArticle(
                    source=source,
                    title=title,
                    url=url,
                    summary=_limit(summary, MAX_SUMMARY_CHARS),
                    published_at=published_at,
                    keywords=_extract_keywords(f"{title} {summary}"),
                    reference_point=_reference_point(title, summary),
                    incomplete=not summary,
                )
            )
    return articles


def _google_news_rss(query: str) -> list[ReferenceArticle]:
    response = requests.get(
        GOOGLE_NEWS_RSS_URL,
        params={"q": query, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"},
        headers=_headers(),
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    articles: list[ReferenceArticle] = []
    for item in root.findall(".//item"):
        raw_title = _xml_text(item, "title")
        title, source = _split_google_news_title(raw_title)
        url = _clean_url(_xml_text(item, "link"))
        summary = _clean_text(_xml_text(item, "description"))
        source = _xml_text(item, "source") or source
        published_at = _format_pub_date(_xml_text(item, "pubDate"))
        if title and url:
            articles.append(
                ReferenceArticle(
                    source=source or _source_from_url(url) or "Google News RSS",
                    title=title,
                    url=url,
                    summary=_limit(summary, MAX_SUMMARY_CHARS),
                    published_at=published_at,
                    keywords=_extract_keywords(f"{title} {summary}"),
                    reference_point=_reference_point(title, summary),
                    incomplete=not summary,
                )
            )
    return articles


def _bing_web_results(query: str) -> list[ReferenceArticle]:
    response = requests.get(
        BING_WEB_URL,
        params={"q": query},
        headers=_headers(),
        timeout=SEARCH_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    parser = BingResultParser()
    parser.feed(response.text)
    return parser.articles


def _enrich_article(article: ReferenceArticle) -> ReferenceArticle:
    host = urlparse(article.url).hostname or ""
    if any(blocked in host for blocked in BLOCKED_HOST_KEYWORDS):
        return ReferenceArticle(
            source=article.source,
            title=article.title,
            url=article.url,
            summary=article.summary,
            published_at=article.published_at,
            keywords=article.keywords,
            reference_point=article.reference_point or "该平台内容不做强行抓取，仅使用搜索结果标题和摘要作为话题参考。",
            short_quote="",
            incomplete=True,
        )

    try:
        response = requests.get(
            article.url,
            headers=_headers(),
            timeout=FETCH_TIMEOUT_SECONDS,
            stream=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "text/html" not in content_type.lower():
            return article
        raw = _read_limited_response(response, MAX_FETCH_BYTES)
    except requests.RequestException:
        return article

    parser = ArticleHTMLParser()
    parser.feed(raw)
    title = parser.title or article.title
    summary = parser.description or parser.first_paragraph or article.summary
    short_quote = _short_quote(parser.first_paragraph)
    keywords = _extract_keywords(f"{title} {summary} {' '.join(parser.paragraphs[:3])}")
    return ReferenceArticle(
        source=parser.site_name or article.source or _source_from_url(article.url),
        title=_limit(title, 90),
        url=article.url,
        summary=_limit(summary, MAX_SUMMARY_CHARS),
        published_at=parser.published_at or article.published_at,
        keywords=keywords or article.keywords,
        reference_point=_reference_point(title, summary),
        short_quote=short_quote,
        incomplete=not (title and summary and article.url),
    )


class BingResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.articles: list[ReferenceArticle] = []
        self._in_h2 = False
        self._in_anchor = False
        self._in_caption = False
        self._href = ""
        self._title_parts: list[str] = []
        self._caption_parts: list[str] = []
        self._pending: dict[str, str] | None = None
        self._capture_text = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = attr.get("class", "")
        if tag == "h2":
            self._in_h2 = True
            self._title_parts = []
            self._href = ""
        elif self._in_h2 and tag == "a":
            self._in_anchor = True
            self._href = _clean_url(attr.get("href") or "")
        elif tag in {"p", "div"} and ("b_caption" in classes or self._pending):
            self._in_caption = True
            self._caption_parts = []
        elif tag == "a" and attr.get("href") and not self._pending:
            href = _clean_url(attr.get("href") or "")
            if _looks_like_result_url(href):
                self._in_anchor = True
                self._href = href
                self._title_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            if not self._in_h2 and not self._pending:
                title = _clean_text("".join(self._title_parts))
                if title and self._href and len(title) > 6:
                    self._pending = {"title": title, "url": self._href}
            self._in_anchor = False
        elif tag == "h2" and self._in_h2:
            title = _clean_text("".join(self._title_parts))
            if title and self._href:
                self._pending = {"title": title, "url": self._href}
            self._in_h2 = False
        elif tag in {"p", "div"} and self._in_caption:
            if self._pending:
                summary = _clean_text("".join(self._caption_parts))
                self.articles.append(
                    ReferenceArticle(
                        source=_source_from_url(self._pending["url"]),
                        title=self._pending["title"],
                        url=self._pending["url"],
                        summary=_limit(summary, MAX_SUMMARY_CHARS),
                        keywords=_extract_keywords(f"{self._pending['title']} {summary}"),
                        reference_point=_reference_point(self._pending["title"], summary),
                        incomplete=not summary,
                    )
                )
                self._pending = None
            self._in_caption = False

    def handle_data(self, data: str) -> None:
        if self._in_anchor:
            self._title_parts.append(data)
        elif self._in_caption:
            self._caption_parts.append(data)


class ArticleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self.site_name = ""
        self.published_at = ""
        self.paragraphs: list[str] = []
        self._in_title = False
        self._in_p = False
        self._title_parts: list[str] = []
        self._p_parts: list[str] = []

    @property
    def first_paragraph(self) -> str:
        return self.paragraphs[0] if self.paragraphs else ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._in_title = True
            self._title_parts = []
        elif tag == "meta":
            name = attr.get("name", "").lower()
            prop = attr.get("property", "").lower()
            content = _clean_text(attr.get("content", ""))
            if not content:
                return
            if name == "description" or prop == "og:description":
                self.description = self.description or _limit(content, MAX_SUMMARY_CHARS)
            elif prop == "og:site_name":
                self.site_name = self.site_name or content
            elif prop in {"article:published_time", "og:published_time"} or name in {"pubdate", "publishdate"}:
                self.published_at = self.published_at or _format_pub_date(content)
        elif tag == "p":
            self._in_p = True
            self._p_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._in_title:
            self.title = _clean_text("".join(self._title_parts))
            self._in_title = False
        elif tag == "p" and self._in_p:
            paragraph = _clean_text("".join(self._p_parts))
            if len(paragraph) >= 18 and len(self.paragraphs) < 6:
                self.paragraphs.append(paragraph)
            self._in_p = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_p:
            self._p_parts.append(data)


def _cache_path(cache_dir: Path | None, *, keyword: str, role: str, limit: int) -> Path | None:
    if cache_dir is None:
        return None
    safe = re.sub(r"[^A-Za-z0-9_\-\u4e00-\u9fff]+", "_", f"{keyword}_{role}_{limit}")[:80]
    return cache_dir / "reference_search" / f"{safe}.json"


def _read_cached(path: Path) -> ReferenceSearchResult | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    created_at = float(raw.get("created_at", 0))
    if time.time() - created_at > 3600:
        return None
    articles = [ReferenceArticle(**item) for item in raw.get("articles", []) if isinstance(item, dict)]
    return ReferenceSearchResult(
        keyword=str(raw.get("keyword", "")),
        role=str(raw.get("role", "owner")),
        articles=articles,
        high_frequency_points=[str(item) for item in raw.get("high_frequency_points", [])],
        searched_queries=[str(item) for item in raw.get("searched_queries", [])],
        warnings=[str(item) for item in raw.get("warnings", [])],
    )


def _write_cached(path: Path, result: ReferenceSearchResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = result.to_dict()
    data["created_at"] = time.time()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _dedupe_articles(articles: list[ReferenceArticle]) -> list[ReferenceArticle]:
    seen: set[str] = set()
    unique: list[ReferenceArticle] = []
    for article in articles:
        key = article.url or article.title
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(article)
    return unique


def _is_generic_title(title: str) -> bool:
    title = _clean_text(title)
    return title in {"新闻", "资讯", "首页", "热点", "搜索"} or len(title) < 4


def _split_google_news_title(value: str) -> tuple[str, str]:
    value = _clean_text(value)
    if " - " not in value:
        return value, "Google News RSS"
    title, source = value.rsplit(" - ", 1)
    return title.strip(), source.strip()


def _looks_like_result_url(url: str) -> bool:
    if not url.startswith("http"):
        return False
    host = urlparse(url).hostname or ""
    if any(skip in host for skip in ["bing.com", "microsoft.com", "go.microsoft.com"]):
        return False
    return True


def _high_frequency_points(articles: list[ReferenceArticle]) -> list[str]:
    counter: Counter[str] = Counter()
    for article in articles:
        counter.update(article.keywords or [])
    return [word for word, _ in counter.most_common(8)]


def _reference_point(title: str, summary: str) -> str:
    text = summary or title
    if not text:
        return "用于参考热点背景/用户讨论/行业观点"
    return f"用于参考：{_limit(text, 64)}"


def _extract_keywords(text: str) -> list[str]:
    return [item for item in KEYWORD_CANDIDATES if item in text][:8]


def _short_quote(text: str) -> str:
    text = _clean_text(text)
    if not text:
        return ""
    sentence = re.split(r"[。！？!?]", text)[0]
    return _limit(sentence, MAX_QUOTE_CHARS)


def _xml_text(item: ET.Element, name: str) -> str:
    node = item.find(name)
    return _clean_text(node.text or "") if node is not None else ""


def _read_limited_response(response: requests.Response, limit: int) -> str:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=16384):
        if not chunk:
            continue
        chunks.append(chunk)
        total += len(chunk)
        if total >= limit:
            break
    encoding = response.encoding or "utf-8"
    return b"".join(chunks).decode(encoding, errors="ignore")


def _clean_url(url: str) -> str:
    url = unescape(url.strip())
    if "bing.com/ck/a" in url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("u", "url"):
            if qs.get(key):
                value = qs[key][0]
                if value.startswith("a1"):
                    value = value[2:]
                try:
                    return unquote(value)
                except Exception:
                    return value
    return url


def _source_from_url(url: str) -> str:
    host = urlparse(url).hostname or ""
    host = host.replace("www.", "")
    if not host:
        return "未标明来源"
    if "mp.weixin.qq.com" in host:
        return "微信公众号公开文章"
    if "baidu.com" in host:
        return "百度搜索结果"
    if "bing.com" in host:
        return "Bing搜索结果"
    if "xiaohongshu.com" in host:
        return "小红书公开话题"
    if "douyin.com" in host:
        return "抖音公开话题"
    if "dianping.com" in host:
        return "大众点评公开页面"
    return host


def _format_pub_date(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:30]


def _clean_text(value: str) -> str:
    value = unescape(value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _limit(value: str, max_chars: int) -> str:
    value = _clean_text(value)
    return value if len(value) <= max_chars else value[:max_chars].rstrip() + "..."


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
