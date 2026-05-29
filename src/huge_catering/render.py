from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import Article


def render_article_html(
    article: Article,
    *,
    brand_name: str,
    inline_image_url: str | None = None,
    inline_images: dict[str, str] | None = None,
    output_path: Path,
) -> str:
    template_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )
    html = env.get_template("article.html.j2").render(
        article=article,
        brand_name=brand_name,
        inline_images=inline_images or ({"after_intro": inline_image_url} if inline_image_url else {}),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return html
