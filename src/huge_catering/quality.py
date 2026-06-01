from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from .models import Article


IMAGE_PLACEHOLDER = "【图片插入位：请在这里插入本期配图】"


@dataclass(frozen=True)
class QualityCheck:
    name: str
    ok: bool
    message: str


def check_article_quality(article: Article, html: str) -> list[dict[str, object]]:
    text = _plain_text(html)
    checks = [
        QualityCheck("标题", bool(article.title.strip()), "已生成标题" if article.title.strip() else "缺少标题"),
        QualityCheck("图片插入位", IMAGE_PLACEHOLDER in html, "已包含图片插入位" if IMAGE_PLACEHOLDER in html else "缺少图片插入位"),
        _check("餐饮经营", _contains_any(text, ["餐饮", "门店", "老板", "客流", "客单", "毛利", "复购", "菜单"]), "内容围绕餐饮经营", "餐饮经营相关性不足"),
        _check("避免空话", not _contains_any(text, ["赋能", "闭环", "抓手", "长期主义", "认知升级"]), "未发现明显空话套话", "存在空话套话"),
        _check("具体动作", _contains_any(text, ["检查", "调整", "复盘", "记录", "菜单", "话术", "清单", "步骤", "今天"]), "包含具体动作", "缺少可执行动作"),
        _check("公众号排版", "<section" in html and "<p" in html, "适合公众号排版", "排版结构不足"),
        _check("重复段落", not _has_repeated_paragraph(text), "未发现重复段落", "存在重复段落"),
        _check("明显错别字", not _contains_any(text, ["的的", "了了", "餐饮饮", "老板板"]), "未发现明显错别字", "存在明显错别字"),
    ]
    return [asdict(item) for item in checks]


def _check(name: str, ok: bool, ok_message: str, fail_message: str) -> QualityCheck:
    return QualityCheck(name, ok, ok_message if ok else fail_message)


def _plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _has_repeated_paragraph(text: str) -> bool:
    parts = [part.strip() for part in re.split(r"[。！？\n]+", text) if len(part.strip()) >= 12]
    seen: set[str] = set()
    for part in parts:
        if part in seen:
            return True
        seen.add(part)
    return False
