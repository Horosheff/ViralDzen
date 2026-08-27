from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from viraldzen.dzen import DzenApi
from viraldzen.html_table import export_html
from viraldzen.http import DzenClient
from viraldzen.images import download_images
from viraldzen.models import ViralItem
from viraldzen.parse import is_clickbait, matches_topic
from viraldzen.score import mark_viral
from viraldzen.store import ItemStore


@dataclass
class CollectConfig:
    topics: list[str]
    pages: int = 2
    delay_seconds: float = 0.7
    min_views: int = 0
    top_n: int = 40
    fetch_content: bool = True
    download_images: bool = True
    recirc: bool = True
    include_feed: bool = True
    recirc_seeds: int = 5
    out_dir: Path = Path("data")
    db_name: str = "viral.sqlite"
    seed_items: list[ViralItem] = field(default_factory=list)
    channel_only: bool = False
    portable_html: bool = False


def _merge(existing: dict[str, ViralItem], incoming: list[ViralItem]) -> None:
    for item in incoming:
        prev = existing.get(item.url)
        if prev is None:
            existing[item.url] = item
            continue
        if item.views > prev.views:
            prev.views = item.views
        if item.views_till_end > prev.views_till_end:
            prev.views_till_end = item.views_till_end
        if item.likes > prev.likes:
            prev.likes = item.likes
        if item.comments > prev.comments:
            prev.comments = item.comments
        if len(item.full_text) > len(prev.full_text):
            prev.full_text = item.full_text
        if len(item.snippet) > len(prev.snippet):
            prev.snippet = item.snippet
        if item.cover_image_url and not prev.cover_image_url:
            prev.cover_image_url = item.cover_image_url
        if len(item.image_urls) > len(prev.image_urls):
            prev.image_urls = item.image_urls
        if item.recirc_parent_url and not prev.recirc_parent_url:
            prev.recirc_parent_url = item.recirc_parent_url
        if item.source_kind == "recirc" and prev.source_kind == "feed":
            prev.source_kind = "recirc"


def _label_seeds(items: list[ViralItem], topic: str) -> list[ViralItem]:
    if not topic:
        return list(items)
    for item in items:
        if not item.topic:
            item.topic = topic
    return list(items)


def keep_item(item: ViralItem, *, channel_only: bool, seed_urls: set[str]) -> bool:
    if channel_only or item.url in seed_urls or item.source_kind == "search":
        return True
    return matches_topic(item, item.topic)


def _apply_article(target: ViralItem, article: ViralItem) -> None:
    if article.publication_id:
        target.publication_id = article.publication_id
    target.full_text = article.full_text or target.full_text
    target.snippet = article.snippet or target.snippet
    if article.title:
        target.title = article.title
    if article.published_at:
        target.published_at = article.published_at
    if article.channel_name:
        target.channel_name = article.channel_name
    if article.channel_url:
        target.channel_url = article.channel_url
    if article.channel_id:
        target.channel_id = article.channel_id
    if article.channel_subscribers:
        target.channel_subscribers = article.channel_subscribers
    if article.views:
        target.views = max(target.views, article.views)
    if article.views_till_end:
        target.views_till_end = max(target.views_till_end, article.views_till_end)
    if article.likes:
        target.likes = max(target.likes, article.likes)
    if article.comments:
        target.comments = max(target.comments, article.comments)
    if article.time_to_read_seconds:
        target.time_to_read_seconds = article.time_to_read_seconds
    if article.cover_image_url:
        target.cover_image_url = article.cover_image_url
    if article.image_urls:
        merged = list(target.image_urls)
        for url in article.image_urls:
            if url not in merged:
                merged.append(url)
        target.image_urls = merged
    if article.tags:
        target.tags = article.tags


def collect(config: CollectConfig) -> dict[str, Any]:
    out_dir = Path(config.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    db_path = out_dir / config.db_name
    csv_path = out_dir / "viral.csv"
    cookie_path = out_dir / "cookies.txt"

    client = DzenClient(cookie_path=cookie_path, delay_seconds=config.delay_seconds)
    client.warmup()
    api = DzenApi(client)
    by_url: dict[str, ViralItem] = {}
    default_topic = next((topic.strip() for topic in config.topics if topic.strip()), "")
    seed_urls = {item.url for item in config.seed_items if item.url}
    if config.seed_items:
        _merge(by_url, _label_seeds(config.seed_items, default_topic))

    if not config.channel_only:
        for topic in config.topics:
            topic = topic.strip()
            if not topic:
                continue
            found = api.search_topic(topic, pages=config.pages)
            _merge(by_url, found)
            if config.include_feed:
                feed_items = api.trending_feed(topic, pages=1)
                matching = [item for item in feed_items if matches_topic(item, topic)]
                _merge(by_url, matching)

    candidates = list(by_url.values())
    if config.min_views:
        candidates = [item for item in candidates if item.views >= config.min_views]
    candidates = [
        item
        for item in candidates
        if keep_item(item, channel_only=config.channel_only, seed_urls=seed_urls)
    ]
    ranked = mark_viral(candidates, min_views=config.min_views)
    pool = [item for item in ranked if not is_clickbait(item.title)] or ranked

    if config.recirc and not config.channel_only:
        seeds = [
            item
            for item in pool
            if item.source_kind == "search" and matches_topic(item, item.topic) and not is_clickbait(item.title)
        ][: config.recirc_seeds]
        for seed in seeds:
            offers = api.recirc_offers(seed, pages=1)
            _merge(by_url, offers)
        on_topic = [
            item
            for item in by_url.values()
            if keep_item(item, channel_only=False, seed_urls=seed_urls)
        ]
        if config.min_views:
            on_topic = [item for item in on_topic if item.views >= config.min_views or item.source_kind == "search"]
        ranked = mark_viral(on_topic, min_views=config.min_views)
        pool = [item for item in ranked if not is_clickbait(item.title)] or ranked

    fetch_pool = pool[: max(config.top_n * 2, config.top_n)]
    if config.fetch_content:
        for item in fetch_pool:
            article = api.fetch_article(item.url, topic=item.topic)
            if article is not None:
                _apply_article(item, article)
        fetch_pool = mark_viral(fetch_pool, min_views=config.min_views)
        clean_fetched = [item for item in fetch_pool if not is_clickbait(item.title)]
        selected = (clean_fetched or fetch_pool)[: max(config.top_n, 1)]
    else:
        selected = fetch_pool[: max(config.top_n, 1)]

    if config.download_images:
        for item in selected:
            if item.cover_image_url or item.image_urls:
                download_images(client, item, images_dir=images_dir)

    now = datetime.now(timezone.utc).isoformat()
    for item in selected:
        item.collected_at = now

    html_path = out_dir / "viral.html"
    store = ItemStore(db_path)
    try:
        store.upsert_many(selected)
        store.export_csv(csv_path)
        export_html(store.all_items(), html_path, portable=config.portable_html)
    finally:
        store.close()

    return {
        "db": db_path,
        "csv": csv_path,
        "html": html_path,
        "images": images_dir,
        "count": len(selected),
    }
