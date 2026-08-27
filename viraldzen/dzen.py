from __future__ import annotations

from typing import Any

from viraldzen.http import DzenClient, build_url
from viraldzen.models import OfficialTopic, ViralItem
from viraldzen.parse import (
    canonical_article_url,
    extra_search_queries,
    find_publishers_ssr,
    is_clickbait,
    iter_feed_items,
    matches_topic,
    next_search_link,
    normalize_card,
    parse_article_ssr,
    parse_official_topic,
)


SEARCH_ENDPOINT = "https://dzen.ru/api/web/v1/zen-search"
EXPORT_ENDPOINT = "https://dzen.ru/api/v3/launcher/export"


class DzenApi:
    def __init__(self, client: DzenClient) -> None:
        self.client = client

    def search_topic(
        self,
        topic: str,
        pages: int = 2,
        type_filter: str = "brief,article",
    ) -> list[ViralItem]:
        url = build_url(
            SEARCH_ENDPOINT,
            {
                "country_code": "ru",
                "forced_request_type": "media_search",
                "count_content": 20,
                "query": topic,
                "clid": 1400,
                "type_filter": type_filter,
                "lang": "ru",
            },
        )
        collected: list[ViralItem] = []
        seen: set[str] = set()
        for _page in range(max(pages, 1)):
            payload = self.client.get_json(url)
            for raw in iter_feed_items(payload):
                item = normalize_card(raw, topic=topic, source_kind="search")
                if item is None or item.url in seen:
                    continue
                seen.add(item.url)
                collected.append(item)
            nxt = next_search_link(payload)
            if not nxt:
                break
            url = nxt
        return collected

    def search_official_topics(self, query: str, pages: int = 1) -> list[OfficialTopic]:
        url = build_url(
            SEARCH_ENDPOINT,
            {
                "country_code": "ru",
                "forced_request_type": "topic_channel_search",
                "count_content": 20,
                "query": query,
                "clid": 1400,
                "type_filter": "topic_channel",
                "lang": "ru",
            },
        )
        collected: list[OfficialTopic] = []
        seen: set[str] = set()
        for _page in range(max(pages, 1)):
            payload = self.client.get_json(url)
            for raw in iter_feed_items(payload):
                topic = parse_official_topic(raw, query=query)
                if topic is None or topic.slug in seen:
                    continue
                seen.add(topic.slug)
                collected.append(topic)
            nxt = next_search_link(payload)
            if not nxt:
                break
            url = nxt
        return collected

    def trending_feed(self, topic: str, pages: int = 1) -> list[ViralItem]:
        url = build_url(
            EXPORT_ENDPOINT,
            {"country_code": "ru", "clid": 1400, "lang": "ru"},
        )
        collected: list[ViralItem] = []
        seen: set[str] = set()
        for page in range(max(pages, 1)):
            endpoint = url if page == 0 else url
            if page == 0:
                payload = self.client.get_json(endpoint)
            else:
                more = payload.get("more") if isinstance(payload, dict) else None
                if not (isinstance(more, dict) and more.get("link")):
                    break
                payload = self.client.get_json(str(more["link"]))
            for raw in iter_feed_items(payload):
                item = normalize_card(raw, topic=topic, source_kind="feed")
                if item is None or item.url in seen:
                    continue
                seen.add(item.url)
                collected.append(item)
        return collected

    def channel_feed(self, channel_name: str, topic: str, pages: int = 1) -> list[ViralItem]:
        channel_name = channel_name.strip().strip("/")
        if channel_name.startswith("id/"):
            params: dict[str, Any] = {
                "country_code": "ru",
                "clid": 1400,
                "channel_id": channel_name.split("/", 1)[1],
            }
        else:
            params = {
                "country_code": "ru",
                "clid": 1400,
                "channel_name": channel_name,
            }
        payload = self.client.get_json(build_url(EXPORT_ENDPOINT, params))
        items: list[ViralItem] = []
        seen: set[str] = set()
        for page in range(max(pages, 1)):
            if page > 0:
                more = payload.get("more") if isinstance(payload, dict) else None
                if not (isinstance(more, dict) and more.get("link")):
                    break
                payload = self.client.get_json(str(more["link"]))
            for raw in iter_feed_items(payload):
                item = normalize_card(raw, topic=topic, source_kind="channel")
                if item is None or item.url in seen:
                    continue
                seen.add(item.url)
                items.append(item)
        return items

    def fetch_article(self, url: str, topic: str) -> ViralItem | None:
        html = self.client.get_text(canonical_article_url(url), accept="text/html,application/json;q=0.9")
        ssr = find_publishers_ssr(html)
        if not ssr:
            self.client.warmup()
            html = self.client.get_text(canonical_article_url(url), accept="text/html,application/json;q=0.9")
            ssr = find_publishers_ssr(html)
        if not ssr:
            return None
        return parse_article_ssr(ssr, url=url, topic=topic)

    def recirc_offers(self, seed: ViralItem, pages: int = 1) -> list[ViralItem]:
        """Related materials around a seed: extra topic queries and the author's channel."""
        related: list[ViralItem] = []
        for query in extra_search_queries(seed.topic, seed.title):
            related.extend(self.search_topic(query, pages=pages))
        channel_key = ""
        if seed.channel_url:
            path = seed.channel_url.rstrip("/").split("dzen.ru/", 1)[-1]
            channel_key = path.strip("/")
        if channel_key:
            related.extend(self.channel_feed(channel_key, topic=seed.topic))
        merged: list[ViralItem] = []
        seen = {seed.url}
        for item in related:
            if item.url in seen:
                continue
            if is_clickbait(item.title):
                continue
            if not matches_topic(item, seed.topic):
                continue
            seen.add(item.url)
            item.source_kind = "recirc"
            item.topic = seed.topic
            item.recirc_parent_url = seed.url
            merged.append(item)
        return merged
