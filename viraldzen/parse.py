from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from viraldzen.models import OfficialTopic, ViralItem, unix_to_iso

AVATARS_HOST = "https://avatars.dzeninfra.ru"


def as_int(value: Any) -> int:
    if value in (None, "", False):
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace("\xa0", " ").replace(" ", "")
    text = text.replace(",", ".")
    multiplier = 1
    lowered = text.lower()
    if lowered.endswith("k") or "тыс" in lowered:
        multiplier = 1000
        text = re.sub(r"[^\d.]", "", text)
    elif lowered.endswith("m") or "млн" in lowered:
        multiplier = 1_000_000
        text = re.sub(r"[^\d.]", "", text)
    else:
        text = re.sub(r"[^\d.]", "", text)
    if not text:
        return 0
    try:
        return int(float(text) * multiplier)
    except ValueError:
        return 0


def first(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def canonical_article_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return url.split("?")[0]
    return f"https://dzen.ru{path}"


def slug_from_topic_url(url: str) -> str:
    if not url:
        return ""
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "topic":
        return parts[1]
    return ""


def parse_official_topic(raw: dict[str, Any], query: str = "") -> OfficialTopic | None:
    card_type = str(first(raw.get("type"), raw.get("itemType"), raw.get("item_type")) or "")
    info = raw.get("topicChannelInfo") or raw.get("topic_channel_info")
    if card_type not in {"search_topic_channel_card", "topic_channel"} and not isinstance(info, dict):
        return None
    if not isinstance(info, dict):
        info = raw
    title = str(first(info.get("title"), raw.get("title"), "") or "").strip()
    feed = str(
        first(
            info.get("feedLink"),
            info.get("feed_link"),
            info.get("url"),
            raw.get("shareLink"),
            raw.get("share_link"),
            "",
        )
        or ""
    )
    slug = slug_from_topic_url(feed)
    if not title or not slug:
        return None
    topic_id = str(
        first(info.get("id"), info.get("strongestId"), info.get("strongest_id"), raw.get("id"), slug)
        or slug
    )
    if topic_id.startswith("topic_channel:"):
        topic_id = topic_id.split(":", 1)[1]
    subscribers = as_int(
        first(
            info.get("subscribers"),
            info.get("subscribersCount"),
            info.get("formatted_subscribers"),
            info.get("formattedSubscribers"),
        )
    )
    url = feed.split("?")[0] if feed.startswith("http") else f"https://dzen.ru/topic/{slug}"
    logo = str(first(info.get("logo"), info.get("logoUrl"), "") or "")
    return OfficialTopic(
        topic_id=topic_id,
        slug=slug,
        title=title,
        subscribers=subscribers,
        url=url,
        logo_url=logo,
        query=query,
    )


def publication_id_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2 and parts[0] in {"a", "b"}:
        return parts[1]
    if parts:
        return parts[-1]
    return url


def image_url_from_obj(image: Any, size: str = "scale_1200") -> str | None:
    if not image:
        return None
    if isinstance(image, str) and image.startswith("http"):
        return image.replace("http://", "https://")
    if not isinstance(image, dict):
        return None
    template = image.get("urlTemplate") or image.get("url_template")
    if template:
        namespace = str(image.get("namespace") or "zen_doc")
        url = template.replace("{namespace}", namespace).replace("{size}", size)
        return url.replace("http://", "https://")
    direct = first(image.get("url"), image.get("src"), image.get("link"))
    if isinstance(direct, str) and direct.startswith("http"):
        return direct.replace("http://", "https://")
    namespace = image.get("namespace")
    group_id = image.get("groupId") or image.get("group_id") or 271828
    image_name = image.get("imageName") or image.get("image_name") or image.get("id")
    if namespace and image_name:
        return f"{AVATARS_HOST}/get-{namespace}/{group_id}/{image_name}/{size}"
    return None


def _source_dict(raw: dict[str, Any]) -> dict[str, Any]:
    source = raw.get("source")
    return source if isinstance(source, dict) else {}


def _social_dict(raw: dict[str, Any]) -> dict[str, Any]:
    social = raw.get("socialInfo") or raw.get("social_info")
    return social if isinstance(social, dict) else {}


def normalize_card(raw: dict[str, Any], topic: str, source_kind: str) -> ViralItem | None:
    item_type = str(first(raw.get("itemType"), raw.get("item_type"), raw.get("type")) or "")
    if item_type in {"hidden", "ad", "news_container", "video_container", "short_video_carousel"}:
        return None
    title = str(first(raw.get("title"), "") or "").strip()
    link = str(
        first(
            raw.get("shareLink"),
            raw.get("share_link"),
            raw.get("link"),
        )
        or ""
    )
    url = canonical_article_url(link)
    if not title or not url:
        return None
    if "/video/" in url or "/shorts/" in url:
        return None
    pub_id = str(
        first(
            raw.get("publication_id"),
            publication_id_from_url(url),
            raw.get("id"),
        )
        or url
    )
    if pub_id.startswith("native:"):
        pub_id = pub_id.split(":", 1)[1]
    source = _source_dict(raw)
    social = _social_dict(raw)
    views = as_int(first(raw.get("views"), raw.get("publicationStatistics", {}).get("views") if isinstance(raw.get("publicationStatistics"), dict) else None))
    views_till_end = as_int(
        first(
            raw.get("viewsTillEnd"),
            raw.get("views_till_end"),
            raw.get("publicationStatistics", {}).get("viewsTillEnd")
            if isinstance(raw.get("publicationStatistics"), dict)
            else None,
        )
    )
    cover = image_url_from_obj(raw.get("image") or raw.get("common_image") or raw.get("image_squared"))
    channel_url_raw = str(first(source.get("shareLink"), source.get("url"), source.get("link"), "") or "")
    channel_url = canonical_article_url(channel_url_raw) if channel_url_raw.startswith("http") else (
        f"https://dzen.ru/{channel_url_raw}" if channel_url_raw else ""
    )
    image_urls = [cover] if cover else []
    published = first(
        raw.get("publicationDate"),
        raw.get("publication_date"),
        raw.get("date"),
        raw.get("creation_time"),
    )
    item = ViralItem(
        publication_id=str(pub_id),
        url=url,
        title=title,
        topic=topic,
        source_kind=source_kind,
        snippet=str(first(raw.get("text"), raw.get("snippet"), "") or "").strip(),
        published_at=unix_to_iso(published),
        channel_name=str(first(source.get("title"), raw.get("domain_title"), "") or ""),
        channel_url=channel_url,
        channel_id=str(first(source.get("id"), source.get("publisher_id"), raw.get("publisher_id"), "") or ""),
        channel_subscribers=as_int(source.get("subscribers")) or None,
        views=views,
        views_till_end=views_till_end,
        likes=as_int(first(social.get("likesCount"), social.get("likeCount"), raw.get("likes"))),
        comments=as_int(first(social.get("commentCount"), social.get("commentsCount"), raw.get("comments"))),
        time_to_read_seconds=as_int(first(raw.get("timeToReadSeconds"), raw.get("time_to_read_seconds"))) or None,
        cover_image_url=cover or "",
        image_urls=image_urls,
        item_type=item_type or "article",
        tags=extract_tags(raw, source),
    )
    return item


def iter_feed_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    feed = payload.get("feedData") if isinstance(payload.get("feedData"), dict) else None
    raw_items = None
    if feed and isinstance(feed.get("items"), list):
        raw_items = feed["items"]
    elif isinstance(payload.get("items"), list):
        raw_items = payload["items"]
    if not raw_items:
        return []
    out: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        nested = item.get("items")
        if isinstance(nested, list) and item.get("type") in {
            "news_container",
            "video_container",
            "short_video_carousel",
            "card",
        }:
            if item.get("title") or item.get("shareLink") or item.get("share_link") or item.get("link"):
                out.append(item)
            for child in nested:
                if isinstance(child, dict):
                    out.append(child)
        else:
            out.append(item)
    return out


def next_search_link(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    more = payload.get("more")
    if isinstance(more, dict) and more.get("link"):
        return str(more["link"])
    feed = payload.get("feedData")
    if isinstance(feed, dict):
        more = feed.get("more")
        if isinstance(more, dict) and more.get("link"):
            return str(more["link"])
    return None


def extract_params_json_blobs(html: str) -> list[dict[str, Any]]:
    blobs: list[dict[str, Any]] = []
    needle = "var _params=("
    start = 0
    decoder = json.JSONDecoder()
    while True:
        idx = html.find(needle, start)
        if idx < 0:
            break
        cursor = idx + len(needle)
        try:
            obj, end = decoder.raw_decode(html[cursor:])
        except json.JSONDecodeError:
            start = idx + len(needle)
            continue
        if isinstance(obj, dict):
            blobs.append(obj)
        start = cursor + end
    return blobs


def find_publishers_ssr(html: str) -> dict[str, Any] | None:
    for blob in extract_params_json_blobs(html):
        ssr = blob.get("ssrData")
        if isinstance(ssr, dict) and isinstance(ssr.get("publishersResponse"), dict):
            return ssr
    return None


def draftjs_text_and_images(content_state: Any) -> tuple[str, list[str]]:
    if isinstance(content_state, str):
        try:
            content_state = json.loads(content_state)
        except json.JSONDecodeError:
            return content_state.strip(), []
    if not isinstance(content_state, dict):
        return "", []
    draft = content_state.get("draftJsState") or content_state
    blocks = draft.get("blocks") if isinstance(draft, dict) else None
    if not isinstance(blocks, list):
        return "", []
    paragraphs: list[str] = []
    image_ids: list[str] = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "")
        data = block.get("data") if isinstance(block.get("data"), dict) else {}
        if "image" in block_type or data.get("image"):
            image = data.get("image") if isinstance(data.get("image"), dict) else data
            image_id = str((image or {}).get("id") or "").strip()
            if image_id:
                image_ids.append(image_id)
        text = str(block.get("text") or "").strip()
        if not text:
            continue
        if block_type.startswith("header"):
            paragraphs.append(text)
        elif block_type == "unordered-list-item":
            paragraphs.append(f"• {text}")
        elif block_type == "ordered-list-item":
            paragraphs.append(text)
        elif block_type != "atomic:image":
            paragraphs.append(text)
    return "\n\n".join(paragraphs).strip(), image_ids


def parse_article_ssr(ssr: dict[str, Any], url: str, topic: str) -> ViralItem | None:
    publishers = ssr.get("publishersResponse")
    if not isinstance(publishers, dict):
        return None
    data = publishers.get("data")
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    if not isinstance(inner, dict):
        return None
    publication = inner.get("publication")
    publisher = inner.get("publisher") if isinstance(inner.get("publisher"), dict) else {}
    if not isinstance(publication, dict):
        return None
    content = publication.get("content") if isinstance(publication.get("content"), dict) else {}
    preview = content.get("preview") if isinstance(content.get("preview"), dict) else {}
    article_content = content.get("articleContent") if isinstance(content.get("articleContent"), dict) else {}
    content_state = article_content.get("contentState")
    full_text, inline_ids = draftjs_text_and_images(content_state)
    images_map = inner.get("images") if isinstance(inner.get("images"), dict) else {}
    image_urls: list[str] = []
    cover = image_url_from_obj(preview.get("image"))
    if cover:
        image_urls.append(cover)
    for image_id in inline_ids:
        mapped = images_map.get(image_id)
        url_from_map = image_url_from_obj(mapped)
        if url_from_map and url_from_map not in image_urls:
            image_urls.append(url_from_map)
    for mapped in images_map.values():
        url_from_map = image_url_from_obj(mapped)
        if url_from_map and url_from_map not in image_urls:
            image_urls.append(url_from_map)
    stats = publication.get("publicationStatistics") if isinstance(publication.get("publicationStatistics"), dict) else {}
    social_meta = {}
    social_resp = ssr.get("socialMetaResponse")
    if isinstance(social_resp, dict) and isinstance(social_resp.get("items"), list) and social_resp["items"]:
        first_social = social_resp["items"][0]
        if isinstance(first_social, dict) and isinstance(first_social.get("metaInfo"), dict):
            social_meta = first_social["metaInfo"]
    title = str(first(preview.get("title"), data.get("title"), "") or "").strip()
    pub_id = str(publication.get("id") or publication_id_from_url(url))
    nickname = str(publisher.get("nickname") or "")
    channel_url = f"https://dzen.ru/{nickname}" if nickname else (
        f"https://dzen.ru/id/{publisher.get('id')}" if publisher.get("id") else ""
    )
    subscribers = None
    sub_block = inner.get("publisherSubscribersCount")
    if isinstance(sub_block, dict):
        subscribers = as_int(sub_block.get("subscribersCount")) or None
    tags = extract_tags(publication, preview, content)
    item = ViralItem(
        publication_id=pub_id,
        url=canonical_article_url(url),
        title=title,
        topic=topic,
        source_kind="article",
        snippet=str(preview.get("snippet") or "").strip(),
        full_text=full_text,
        published_at=unix_to_iso(first(publication.get("publishTime"), publication.get("addTime"))),
        channel_name=str(publisher.get("name") or ""),
        channel_url=channel_url,
        channel_id=str(publisher.get("id") or ""),
        channel_subscribers=subscribers,
        views=as_int(stats.get("views")),
        views_till_end=as_int(stats.get("viewsTillEnd")),
        likes=as_int(first(social_meta.get("likeCount"), social_meta.get("likesCount"))),
        comments=as_int(first(social_meta.get("commentsCount"), social_meta.get("commentCount"))),
        time_to_read_seconds=as_int(content.get("timeToReadSeconds")) or None,
        cover_image_url=cover or "",
        image_urls=image_urls,
        item_type=str(publication.get("itemType") or content.get("type") or "article"),
        tags=tags,
    )
    return item


def extract_tags(*sources: Any) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for source in sources:
        raw_list: Any
        if isinstance(source, list):
            raw_list = source
        elif isinstance(source, dict):
            raw_list = first(
                source.get("tags"),
                source.get("embeddedTags"),
                source.get("embedded_tags"),
                source.get("topics"),
            )
        else:
            continue
        if not isinstance(raw_list, list):
            continue
        for tag in raw_list:
            name = ""
            if isinstance(tag, str):
                name = tag.strip()
            elif isinstance(tag, dict):
                name = str(first(tag.get("name"), tag.get("title"), tag.get("slug"), "") or "").strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            tags.append(name)
    return tags


_TOKEN_RE = re.compile(r"[0-9A-Za-zА-Яа-яЁё]{3,}", re.UNICODE)
_STOP = {
    "это", "как", "для", "что", "или", "при", "все", "всё", "the", "and",
    "про", "без", "над", "под", "есть", "быть", "этот", "эта", "эти",
    "ваш", "вас", "если", "сможете", "ответить", "вопросов", "тест",
    "тесты", "эрудицию", "умников", "уровне", "числ", "наряды",
    "которые", "который", "которая", "которых", "которого", "которой",
    "часть", "иначе", "просто", "очень", "можно", "нужно", "сегодня",
    "почему", "когда", "будет", "после", "только", "также", "чтобы",
    "более", "менее", "один", "одна", "одно", "люди", "человек",
    "человека", "своей", "свою", "свои", "этой", "этом", "того",
    "уже", "еще", "ещё", "вот", "нам", "вам", "либо", "даже", "ведь",
    "почти", "сразу", "снова", "опять", "между", "перед", "через",
    "около",
}

CLICKBAIT_MARKERS = (
    "если сможете",
    "тест на",
    "8/10",
    "8 из 10",
    "10 вопросов",
    "iq",
    "умников",
    "эрудиц",
)


def topic_tokens(topic: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(topic)} - _STOP


def ordered_content_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text or ""):
        token = match.group(0)
        if token.lower() in _STOP:
            continue
        tokens.append(token)
    return tokens


def matches_topic(item: ViralItem, topic: str) -> bool:
    tokens = topic_tokens(topic)
    if not tokens:
        return True
    hay = f"{item.title} {item.snippet} {item.full_text[:500]} {' '.join(item.tags)} {item.channel_name}".lower()
    if topic.lower() in hay:
        return True
    return any(_token_in_text(token, hay) for token in tokens)


def _token_in_text(token: str, hay: str) -> bool:
    needle = token.lower()
    if needle in hay:
        return True
    if len(needle) < 5:
        return False
    stem = needle[:-1]
    if len(stem) < 4:
        return False
    return any(
        match.group(0).lower().startswith(stem) for match in _TOKEN_RE.finditer(hay)
    )


def is_clickbait(title: str) -> bool:
    lowered = title.lower()
    return any(marker in lowered for marker in CLICKBAIT_MARKERS)


def extra_search_queries(topic: str, title: str) -> list[str]:
    title_tokens = [tok for tok in sorted(topic_tokens(title), key=len, reverse=True) if tok not in topic_tokens(topic)]
    if not title_tokens:
        return []
    queries = [f"{topic} {title_tokens[0]}"]
    if len(title_tokens) >= 2:
        queries.append(f"{topic} {title_tokens[0]} {title_tokens[1]}")
    return queries
