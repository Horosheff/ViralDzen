from __future__ import annotations

from collections.abc import Callable
from typing import Literal, TextIO, assert_never

from viraldzen.models import OfficialTopic

SortMode = Literal["search", "subscribers"]

_ALL_TOKENS = {"all", "все", "*"}
_MAX_PROMPT_TRIES = 3


def format_subscribers(count: int) -> str:
    return f"{count:,}".replace(",", " ")


def format_official_topics(topics: list[OfficialTopic], *, limit: int | None = None) -> str:
    rows = topics if limit is None else topics[:limit]
    lines = [
        f"{'#':>3}  {'подписчики':>12}  {'тема':<42}  slug",
        "-" * 92,
    ]
    for index, topic in enumerate(rows, start=1):
        title = topic.title.replace("\n", " ")
        if len(title) > 42:
            title = title[:41] + "…"
        lines.append(
            f"{index:3d}  {format_subscribers(topic.subscribers):>12}  {title:<42}  {topic.slug}"
        )
    return "\n".join(lines)


def parse_selection(text: str, topics: list[OfficialTopic]) -> list[OfficialTopic]:
    raw = text.strip()
    if not raw:
        raise ValueError("пустой выбор")
    lowered = raw.lower()
    if lowered in _ALL_TOKENS:
        if not topics:
            raise ValueError("список официальных тем пуст")
        return list(topics)

    if "," in raw or ";" in raw:
        parts = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
        selected: list[OfficialTopic] = []
        seen: set[str] = set()
        for part in parts:
            for topic in _match_one(part, topics):
                if topic.slug in seen:
                    continue
                seen.add(topic.slug)
                selected.append(topic)
        if not selected:
            raise ValueError(f"ничего не выбрано: {raw}")
        return selected

    return _match_one(raw, topics)


def _match_one(token: str, topics: list[OfficialTopic]) -> list[OfficialTopic]:
    if token.isdigit():
        index = int(token)
        if index < 1 or index > len(topics):
            raise ValueError(f"номер {index} вне списка 1–{len(topics)}")
        return [topics[index - 1]]

    needle = token.strip().lower().lstrip("/")
    if needle.startswith("topic/"):
        needle = needle.split("/", 1)[1]
    slug_hits = [topic for topic in topics if topic.slug.lower() == needle]
    if slug_hits:
        return slug_hits

    title_hits = [topic for topic in topics if topic.title.lower() == token.strip().lower()]
    if len(title_hits) == 1:
        return title_hits
    if len(title_hits) > 1:
        raise ValueError(f"тема «{token}» неоднозначна, укажите slug или номер")

    prefix_hits = [topic for topic in topics if topic.title.lower().startswith(token.strip().lower())]
    if len(prefix_hits) == 1:
        return prefix_hits
    raise ValueError(f"не нашёл официальную тему «{token}»")


def merge_official_topics(groups: list[list[OfficialTopic]]) -> list[OfficialTopic]:
    merged: list[OfficialTopic] = []
    seen: set[str] = set()
    for group in groups:
        for topic in group:
            if topic.slug in seen:
                continue
            seen.add(topic.slug)
            merged.append(topic)
    return merged


def sort_official_topics(topics: list[OfficialTopic], mode: SortMode) -> list[OfficialTopic]:
    if mode == "subscribers":
        return sorted(topics, key=lambda topic: topic.subscribers, reverse=True)
    if mode == "search":
        return list(topics)
    assert_never(mode)


def apply_topic_filters(
    topics: list[OfficialTopic],
    *,
    min_subscribers: int = 0,
    limit: int | None = None,
    sort: SortMode = "search",
) -> list[OfficialTopic]:
    filtered = [topic for topic in topics if topic.subscribers >= min_subscribers]
    filtered = sort_official_topics(filtered, sort)
    if limit is not None:
        filtered = filtered[: max(limit, 0)]
    return filtered


def _topic_heading(prompt_query: str, interactive: bool) -> str:
    if interactive:
        heading = "Куда смотреть? Официальные темы Дзена"
    else:
        heading = "Официальные темы Дзена"
    if prompt_query:
        heading += f" по запросу «{prompt_query}»"
    return heading + ":"


def select_official_topics(
    available: list[OfficialTopic],
    *,
    pick: str | None = None,
    slugs: list[str] | None = None,
    interactive: bool = False,
    prompt_query: str = "",
    show_list: bool = True,
    stdin: TextIO | None = None,
    input_fn: Callable[[str], str] | None = None,
    print_fn: Callable[[str], None] = print,
) -> list[OfficialTopic]:
    """Pick hubs from a Dzen official-topic list.

    Non-interactive default: first item (Dzen search rank). Explicit --pick / --slug
    always win. Interactive mode asks until a valid choice or retries are exhausted.
    """
    if not available:
        return []

    if show_list:
        print_fn(_topic_heading(prompt_query, interactive))
        print_fn(format_official_topics(available))

    slug_list = [slug.strip() for slug in (slugs or []) if slug and slug.strip()]
    if slug_list:
        selected: list[OfficialTopic] = []
        seen: set[str] = set()
        missing: list[str] = []
        for slug in slug_list:
            try:
                matched = _match_one(slug, available)
            except ValueError:
                missing.append(slug)
                continue
            for topic in matched:
                if topic.slug in seen:
                    continue
                seen.add(topic.slug)
                selected.append(topic)
        if missing and not selected:
            raise ValueError("не нашёл slug: " + ", ".join(missing))
        if missing:
            print_fn("Не нашёл slug: " + ", ".join(missing))
        return selected

    if pick:
        return parse_selection(pick, available)

    if interactive:
        print_fn("")
        print_fn("Введите номер, несколько номеров через запятую, slug или «все».")

        def default_reader(message: str) -> str:
            if stdin is not None:
                print_fn(message.rstrip("\n"))
                line = stdin.readline()
                if line == "":
                    raise EOFError
                return line
            return input(message)

        reader: Callable[[str], str] = input_fn if input_fn is not None else default_reader
        last_error = ""
        for _attempt in range(_MAX_PROMPT_TRIES):
            try:
                choice = reader("> ")
            except EOFError as exc:
                raise ValueError("нет ввода для выбора темы") from exc
            try:
                return parse_selection(choice, available)
            except ValueError as exc:
                last_error = str(exc)
                print_fn(f"Не понял выбор: {last_error}. Попробуйте ещё раз.")
        raise ValueError(last_error or "не удалось выбрать тему")

    chosen = available[0]
    print_fn(
        f"Неинтерактивный режим: смотрим «{chosen.title}» ({chosen.slug}). "
        "Уточните --pick или --slug."
    )
    return [chosen]
