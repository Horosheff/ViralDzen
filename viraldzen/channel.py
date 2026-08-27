from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, assert_never
from urllib.parse import urlparse

from viraldzen.dzen import DzenApi
from viraldzen.models import OfficialTopic, ViralItem
from viraldzen.parse import canonical_article_url, ordered_content_tokens, topic_tokens
from viraldzen.topics import apply_topic_filters, merge_official_topics

ChannelKind = Literal["name", "id"]
LinkKind = Literal["channel", "topic", "article"]

_NOT_CHANNEL = {"a", "b", "video", "shorts", "topic", "brief", "live", "search"}


@dataclass(frozen=True)
class ChannelRef:
    kind: ChannelKind
    value: str

    @property
    def export_key(self) -> str:
        if self.kind == "id":
            return f"id/{self.value}"
        if self.kind == "name":
            return self.value
        assert_never(self.kind)

    @property
    def url(self) -> str:
        if self.kind == "id":
            return f"https://dzen.ru/id/{self.value}"
        if self.kind == "name":
            return f"https://dzen.ru/{self.value}"
        assert_never(self.kind)


@dataclass
class PhraseHint:
    phrase: str
    score: int
    source: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChannelStudy:
    ref: ChannelRef
    channel_name: str
    channel_url: str
    item_count: int
    phrases: list[PhraseHint]
    hubs: list[OfficialTopic]
    items: list[ViralItem] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel_name": self.channel_name,
            "channel_url": self.channel_url,
            "export_key": self.ref.export_key,
            "item_count": self.item_count,
            "phrases": [hint.to_dict() for hint in self.phrases],
            "hubs": [hub.to_dict() for hub in self.hubs],
        }


@dataclass(frozen=True)
class DzenLink:
    kind: LinkKind
    channel: ChannelRef | None = None
    slug: str = ""
    article_url: str = ""


def parse_dzen_link(value: str) -> DzenLink:
    text = (value or "").strip()
    if not text:
        raise ValueError("пустая ссылка")
    text = text.lstrip("@")
    if "://" not in text and ("dzen.ru/" in text or "zen.yandex.ru/" in text):
        text = "https://" + text
    if "://" in text:
        parsed = urlparse(text)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host not in {"dzen.ru", "zen.yandex.ru"}:
            raise ValueError(f"это не ссылка на Дзен: {value}")
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("в ссылке нет пути")
        if parts[0] in {"video", "shorts"}:
            raise ValueError("видео и ролики не собираем, нужна статья, хаб или канал")
        if parts[0] == "topic":
            if len(parts) < 2:
                raise ValueError("в ссылке нет slug темы")
            return DzenLink("topic", slug=parts[1])
        if parts[0] in {"a", "b"}:
            return DzenLink("article", article_url=canonical_article_url(text))
        if parts[0] == "id":
            return DzenLink("channel", channel=parse_channel_ref(text))
        if parts[0] in {"brief", "live", "search"}:
            raise ValueError("эта ссылка не канал, не статья и не официальная тема")
        return DzenLink("channel", channel=parse_channel_ref(text))
    if text.startswith("topic/"):
        slug = text.split("/", 1)[1].strip()
        if not slug:
            raise ValueError("пустой slug темы")
        return DzenLink("topic", slug=slug)
    return DzenLink("channel", channel=parse_channel_ref(text))


def parse_channel_ref(value: str) -> ChannelRef:
    text = (value or "").strip()
    if not text:
        raise ValueError("пустая ссылка на канал")
    text = text.lstrip("@")
    if "://" not in text and ("dzen.ru/" in text or "zen.yandex.ru/" in text):
        text = "https://" + text
    if "://" in text:
        parsed = urlparse(text)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        if host not in {"dzen.ru", "zen.yandex.ru"}:
            raise ValueError(f"это не ссылка на Дзен: {value}")
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError("в ссылке нет имени канала")
        if parts[0] in _NOT_CHANNEL:
            raise ValueError("это материал или тема, нужен канал: dzen.ru/<имя> или dzen.ru/id/...")
        if parts[0] == "id":
            if len(parts) < 2:
                raise ValueError("в ссылке нет id канала")
            return ChannelRef("id", parts[1])
        return ChannelRef("name", parts[0])
    if text.startswith("id/"):
        ident = text.split("/", 1)[1].strip()
        if not ident:
            raise ValueError("пустой id канала")
        return ChannelRef("id", ident)
    if "/" in text.strip("/"):
        raise ValueError("нужна ссылка на канал или короткое имя без пути")
    return ChannelRef("name", text.strip("/"))


_WEAK_TITLE_TOKENS = {
    "позволят",
    "взглянуть",
    "проанализируем",
    "вопросы",
    "часть",
    "иначе",
}


def rank_phrases(items: list[ViralItem], limit: int = 8) -> list[PhraseHint]:
    scores: dict[str, int] = {}
    display: dict[str, str] = {}
    tag_score: dict[str, int] = {}
    title_score: dict[str, int] = {}

    def add(phrase: str, weight: int, bucket: dict[str, int]) -> None:
        text = phrase.strip()
        key = text.lower()
        if len(key) < 3:
            return
        if not topic_tokens(text) and " " not in text:
            return
        scores[key] = scores.get(key, 0) + weight
        bucket[key] = bucket.get(key, 0) + weight
        display.setdefault(key, text)

    for item in items:
        for tag in item.tags:
            add(tag, 3, tag_score)
        tokens = [
            token
            for token in ordered_content_tokens(item.title)
            if token.lower() not in _WEAK_TITLE_TOKENS
        ]
        for token in tokens:
            add(token, 1, title_score)
        for left, right in zip(tokens, tokens[1:]):
            add(f"{left} {right}", 2, title_score)

    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    hints: list[PhraseHint] = []
    for key, score in ranked[: max(limit, 0)]:
        tag_part = tag_score.get(key, 0)
        title_part = title_score.get(key, 0)
        if tag_part and title_part:
            source = "mixed"
        elif tag_part:
            source = "tag"
        else:
            source = "title"
        hints.append(PhraseHint(phrase=display[key], score=score, source=source))
    return hints


def _hub_matches_phrase(hub: OfficialTopic, phrase: str) -> bool:
    hay = hub.title.lower()
    needle = phrase.lower()
    if needle in hay:
        return True
    tokens = topic_tokens(phrase)
    return bool(tokens) and any(token in hay for token in tokens)


def study_channel(
    api: DzenApi,
    channel: ChannelRef | str,
    *,
    pages: int = 2,
    enrich: int = 8,
    phrase_limit: int = 8,
    hub_limit: int = 15,
) -> ChannelStudy:
    ref = channel if isinstance(channel, ChannelRef) else parse_channel_ref(channel)
    items = api.channel_feed(ref.export_key, topic="", pages=pages)
    channel_name = ""
    channel_url = ref.url
    ranked = sorted(items, key=lambda item: item.views, reverse=True)
    for item in ranked[: max(enrich, 0)]:
        article = api.fetch_article(item.url, topic=item.topic)
        if article is None:
            continue
        if article.tags:
            item.tags = article.tags
        if article.channel_name:
            item.channel_name = article.channel_name
        if article.channel_url:
            item.channel_url = article.channel_url
    for item in items:
        if item.channel_name and not channel_name:
            channel_name = item.channel_name
        if item.channel_url:
            channel_url = item.channel_url
            break
    phrases = rank_phrases(items, limit=phrase_limit)
    hubs = _hubs_from_phrases(api, phrases, hub_limit=hub_limit)
    return ChannelStudy(
        ref=ref,
        channel_name=channel_name,
        channel_url=channel_url,
        item_count=len(items),
        phrases=phrases,
        hubs=hubs,
        items=items,
    )


def _hubs_from_phrases(
    api: DzenApi,
    phrases: list[PhraseHint],
    *,
    hub_limit: int,
) -> list[OfficialTopic]:
    groups: list[list[OfficialTopic]] = []
    for hint in phrases:
        tokens = topic_tokens(hint.phrase)
        if hint.source == "title" and " " not in hint.phrase and max((len(tok) for tok in tokens), default=0) < 6:
            continue
        found = api.search_official_topics(hint.phrase, pages=1)
        related = [hub for hub in found if _hub_matches_phrase(hub, hint.phrase)]
        if related:
            groups.append(related)
    return apply_topic_filters(
        merge_official_topics(groups),
        min_subscribers=0,
        limit=hub_limit,
        sort="subscribers",
    )


def study_article(
    api: DzenApi,
    url: str,
    *,
    phrase_limit: int = 8,
    hub_limit: int = 15,
) -> ChannelStudy:
    article = api.fetch_article(canonical_article_url(url), topic="")
    if article is None:
        raise ValueError("не удалось открыть статью Дзена")
    phrases = rank_phrases([article], limit=phrase_limit)
    hubs = _hubs_from_phrases(api, phrases, hub_limit=hub_limit)
    nickname = ""
    if article.channel_url:
        try:
            ref = parse_channel_ref(article.channel_url)
        except ValueError:
            ref = ChannelRef("name", article.channel_name or "article")
    else:
        ref = ChannelRef("name", article.channel_name or "article")
        nickname = article.channel_name
    return ChannelStudy(
        ref=ref,
        channel_name=article.channel_name or nickname,
        channel_url=article.channel_url or article.url,
        item_count=1,
        phrases=phrases,
        hubs=hubs,
        items=[article],
    )
