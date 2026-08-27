from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TextIO, assert_never

from viraldzen import __version__
from viraldzen.channel import ChannelStudy, parse_dzen_link, study_article, study_channel
from viraldzen.collect import CollectConfig, collect
from viraldzen.dzen import DzenApi
from viraldzen.html_table import export_html, merge_rows
from viraldzen.http import DzenClient
from viraldzen.models import OfficialTopic, ViralItem
from viraldzen.store import ItemStore
from viraldzen.topics import (
    SortMode,
    apply_topic_filters,
    format_official_topics,
    merge_official_topics,
    select_official_topics,
)


def _load_config(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Config must be a JSON object")
    return data


def _print_table(rows: list, limit: int) -> None:
    print(
        f"{'V':1} {'score':>7} {'views':>8} {'likes':>5} {'date':<20} {'topic':<16} title"
    )
    print("-" * 120)
    for row in rows[:limit]:
        flag = "*" if row["is_viral"] else " "
        published = (row["published_at"] or "")[:19]
        title = (row["title"] or "").replace("\n", " ")[:70]
        print(
            f"{flag:1} {row['viral_score']:7.2f} {row['views']:8d} {row['likes']:5d} "
            f"{published:<20} {(row['topic'] or '')[:16]:<16} {title}"
        )


def _make_api(delay_seconds: float, cookie_path: Path | None = None) -> DzenApi:
    client = DzenClient(cookie_path=cookie_path, delay_seconds=delay_seconds)
    client.warmup()
    return DzenApi(client)


def _prompt_query(stdin: TextIO | None = None) -> str:
    print("О какой теме показать официальные хабы Дзена?")
    try:
        if stdin is not None:
            line = stdin.readline()
            if line == "":
                raise EOFError
            text = line.strip()
        else:
            text = input("> ").strip()
    except EOFError as exc:
        raise SystemExit("Нужен --topic или --slug: нечего спрашивать в этом режиме.") from exc
    if not text:
        raise SystemExit("Пустой запрос. Укажите --topic, например: --topic здоровье")
    return text


def _fetch_official_topics(
    api: DzenApi,
    seeds: list[str],
    *,
    pages: int,
    limit: int,
    min_subscribers: int,
    sort: SortMode,
) -> list[OfficialTopic]:
    groups: list[list[OfficialTopic]] = []
    for seed in seeds:
        seed = seed.strip()
        if not seed:
            continue
        found = api.search_official_topics(seed, pages=pages)
        groups.append(found)
    merged = merge_official_topics(groups)
    return apply_topic_filters(
        merged,
        min_subscribers=min_subscribers,
        limit=limit,
        sort=sort,
    )


def _normalize_slug(value: str) -> str:
    slug = value.strip().lstrip("/")
    if slug.startswith("topic/"):
        slug = slug.split("/", 1)[1]
    return slug


def _resolve_slugs_only(api: DzenApi, slugs: list[str], pages: int) -> list[OfficialTopic]:
    groups: list[list[OfficialTopic]] = []
    normalized = [_normalize_slug(slug) for slug in slugs if _normalize_slug(slug)]
    for slug in normalized:
        query = slug.replace("-", " ")
        groups.append(api.search_official_topics(query, pages=pages))
        if query != slug:
            groups.append(api.search_official_topics(slug, pages=1))
    available = {topic.slug.lower(): topic for topic in merge_official_topics(groups)}
    resolved: list[OfficialTopic] = []
    for slug in normalized:
        found = available.get(slug.lower())
        if found is not None:
            resolved.append(found)
            continue
        resolved.append(
            OfficialTopic(
                topic_id=slug,
                slug=slug,
                title=slug.replace("-", " "),
                subscribers=0,
                url=f"https://dzen.ru/topic/{slug}",
                query=slug,
            )
        )
    return resolved


def _cmd_topics(args: argparse.Namespace) -> int:
    query = (args.query or "").strip()
    if not query:
        query = _prompt_query()
    api = _make_api(args.delay_seconds)
    topics = _fetch_official_topics(
        api,
        [query],
        pages=args.pages,
        limit=args.limit,
        min_subscribers=args.min_subscribers,
        sort=args.sort,
    )
    if not topics:
        raise SystemExit(f"Официальные темы по запросу «{query}» не найдены.")
    if args.json:
        print(json.dumps([topic.to_dict() for topic in topics], ensure_ascii=False, indent=2))
        return 0
    print(f"Официальные темы Дзена по запросу «{query}» ({len(topics)}):")
    print(format_official_topics(topics))
    print("")
    print(f"Дальше: python3 -m viraldzen collect --topic {query} --pick 1")
    print("Или по slug: python3 -m viraldzen collect --slug " + topics[0].slug)
    return 0


def _print_channel_study(study: ChannelStudy) -> None:
    print(f"Канал: {study.channel_name or study.ref.export_key}")
    print(f"URL: {study.channel_url}")
    print(f"Материалов в ленте: {study.item_count}")
    print("")
    print("О чём пишет (слова и теги):")
    if not study.phrases:
        print("  (не удалось вытащить темы из ленты)")
    else:
        for index, hint in enumerate(study.phrases, start=1):
            print(f"  {index}. {hint.phrase}  ({hint.score}, {hint.source})")
    print("")
    if study.hubs:
        print("Похожие официальные темы Дзена:")
        print(format_official_topics(study.hubs))
    else:
        print("Официальных хабов по этим словам не нашлось.")


def _cmd_channel(args: argparse.Namespace) -> int:
    api = _make_api(args.delay_seconds)
    try:
        link = parse_dzen_link(args.url)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if link.kind == "topic":
        query = link.slug.replace("-", " ")
        found = api.search_official_topics(query, pages=max(args.pages, 1))
        match = next((topic for topic in found if topic.slug.lower() == link.slug.lower()), None)
        if args.json:
            payload = {"kind": "topic", "slug": link.slug}
            if match is not None:
                payload["hub"] = match.to_dict()
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print(f"Официальная тема Дзена: {link.slug}")
        if match is not None:
            print(format_official_topics([match]))
        else:
            print("Хаба с таким slug в поиске не нашлось, collect всё равно может взять --slug.")
        print(f"Дальше: python3 -m viraldzen collect --slug {link.slug} --out-dir data")
        return 0
    try:
        if link.kind == "article":
            print("Это статья. Разбираю, о какой теме она.")
            study = study_article(
                api,
                link.article_url,
                phrase_limit=args.phrase_limit,
                hub_limit=args.limit,
            )
        elif link.kind == "channel":
            study = study_channel(
                api,
                link.channel or args.url,
                pages=args.pages,
                enrich=args.enrich,
                phrase_limit=args.phrase_limit,
                hub_limit=args.limit,
            )
        else:
            assert_never(link.kind)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    if args.json:
        print(json.dumps(study.to_dict(), ensure_ascii=False, indent=2))
        return 0
    _print_channel_study(study)
    print("")
    if study.hubs:
        target = study.channel_url if link.kind == "channel" else args.url
        flag = "--channel" if link.kind == "channel" else "--url"
        print(f"Дальше: python3 -m viraldzen collect {flag} {target} --channel-limit 1")
        print("Или по slug: python3 -m viraldzen collect --slug " + study.hubs[0].slug)
    elif study.phrases:
        print(
            "Дальше без хаба: python3 -m viraldzen collect --topic "
            f"{study.phrases[0].phrase} --raw-topic"
        )
    return 0


def _apply_study_to_collect(
    study: ChannelStudy,
    *,
    pick: str | None,
    slugs: list[str],
    interactive: bool,
    channel_limit: int,
    label: str,
) -> tuple[list[OfficialTopic], list[str]]:
    chosen: list[OfficialTopic] = []
    search_topics: list[str] = []
    _print_channel_study(study)
    print("")
    if study.hubs:
        if pick or slugs or (interactive and pick is None):
            try:
                chosen = select_official_topics(
                    study.hubs,
                    pick=pick,
                    slugs=slugs,
                    interactive=interactive and pick is None and not slugs,
                    prompt_query=study.channel_name or study.ref.export_key,
                )
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
        else:
            chosen = study.hubs[: max(channel_limit, 1)]
            print(
                f"Без --pick беру первые {len(chosen)} хаб(а/ов) — это эвристика по тегам "
                "и заголовкам, не «тема канала от Дзена»."
            )
            print("Чтобы выбрать самому: сначала channel --url ..., потом collect --pick 1")
    elif study.phrases:
        search_topics = [hint.phrase for hint in study.phrases[: max(channel_limit, 1)]]
        print("Хабов нет, ищу как есть:", ", ".join(search_topics))
    else:
        raise SystemExit(f"Не нашлось тем для сбора ({label}).")
    if chosen:
        search_topics = [topic.title for topic in chosen]
        print("Смотрим официальные темы:")
        for topic in chosen:
            print(f"  • {topic.title}  [{topic.slug}]  {topic.url}")
    return chosen, search_topics


def _cmd_collect(args: argparse.Namespace) -> int:
    cfg: dict = {}
    if args.config:
        cfg = _load_config(args.config)
    seeds = list(args.topics or cfg.get("topics") or [])
    slugs = list(args.slugs or cfg.get("official_slugs") or cfg.get("slugs") or [])
    channel = (args.channel or cfg.get("channel") or "").strip()
    url = (args.url or cfg.get("url") or "").strip()
    article_url = ""
    channel_limit = (
        args.channel_limit
        if args.channel_limit is not None
        else int(cfg.get("channel_limit", 3))
    )
    pick = args.pick if args.pick is not None else cfg.get("pick")
    if pick is not None:
        pick = str(pick)
    raw_topic = bool(args.raw_topic or cfg.get("raw_topic", False))
    delay = (
        args.delay_seconds
        if args.delay_seconds is not None
        else float(cfg.get("delay_seconds", 0.7))
    )
    topic_pages = (
        args.topic_pages
        if args.topic_pages is not None
        else int(cfg.get("topic_pages", 1))
    )
    topic_limit = (
        args.topic_limit
        if args.topic_limit is not None
        else int(cfg.get("topic_limit", 20))
    )
    min_subscribers = (
        args.min_subscribers
        if args.min_subscribers is not None
        else int(cfg.get("min_subscribers", 0))
    )
    sort_raw = args.topic_sort or cfg.get("topic_sort") or "search"
    if sort_raw == "subscribers":
        sort_mode: SortMode = "subscribers"
    elif sort_raw == "search":
        sort_mode = "search"
    else:
        raise SystemExit("topic_sort must be search or subscribers")
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    channel_only = bool(args.channel_only or cfg.get("channel_only", False))
    portable_html = bool(args.portable or cfg.get("portable", False))

    chosen: list[OfficialTopic] = []
    search_topics: list[str] = []
    seed_items: list[ViralItem] = []

    if url and channel:
        raise SystemExit("Укажите либо --url, либо --channel.")
    if url:
        try:
            link = parse_dzen_link(url)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        if link.kind == "topic":
            slugs = slugs or [link.slug]
        elif link.kind == "article":
            article_url = link.article_url
        elif link.kind == "channel":
            channel = link.channel.url if link.channel is not None else url
        else:
            assert_never(link.kind)

    if channel_only and (seeds or raw_topic or slugs):
        raise SystemExit("--channel-only не сочетается с --topic, --slug и --raw-topic.")
    if channel_only and article_url:
        raise SystemExit("--channel-only нужен со ссылкой на канал, не на статью.")
    if channel_only and not channel:
        raise SystemExit("Для --channel-only укажите --channel или --url канала.")
    if (channel or article_url) and (seeds or raw_topic):
        raise SystemExit("Укажите либо ссылку Дзена, либо --topic, не оба сразу.")

    if channel or article_url:
        cookie_path = args.out_dir / "cookies.txt"
        api = _make_api(delay, cookie_path=cookie_path)
        try:
            if article_url:
                print("Это статья. Разбираю тему, затем собираю вирусное по хабам.")
                study = study_article(
                    api,
                    article_url,
                    hub_limit=max(topic_limit, channel_limit),
                )
                label = "статья"
            else:
                study = study_channel(
                    api,
                    channel,
                    pages=max(topic_pages, 1),
                    hub_limit=max(topic_limit, channel_limit),
                )
                label = "канал"
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
        seed_items = list(study.items)
        if channel_only:
            _print_channel_study(study)
            print("")
            search_topics = [study.channel_name or study.ref.export_key]
            print(f"Собираю ленту канала, без поиска по всему Дзену: {search_topics[0]}")
            if not seed_items:
                raise SystemExit("В ленте канала нет статей для сбора.")
        else:
            chosen, search_topics = _apply_study_to_collect(
                study,
                pick=pick,
                slugs=slugs,
                interactive=interactive,
                channel_limit=channel_limit,
                label=label,
            )
    elif raw_topic:
        if not seeds:
            raise SystemExit("Для --raw-topic нужен --topic или список topics в конфиге.")
        search_topics = [seed.strip() for seed in seeds if seed.strip()]
        print("Ищем как есть, без выбора официальной темы:", ", ".join(search_topics))
    else:
        cookie_path = args.out_dir / "cookies.txt"
        api = _make_api(delay, cookie_path=cookie_path)
        if not seeds and not slugs:
            if interactive:
                seeds = [_prompt_query()]
            else:
                raise SystemExit(
                    "Укажите --topic, --slug, --channel или --url."
                )
        if slugs and not seeds:
            chosen = _resolve_slugs_only(api, slugs, pages=topic_pages)
        elif (
            len(seeds) > 1
            and pick is None
            and not slugs
            and not interactive
        ):
            print("Несколько запросов: для каждого беру главную официальную тему Дзена.")
            seen_slugs: set[str] = set()
            fallbacks: list[str] = []
            for seed in seeds:
                group = _fetch_official_topics(
                    api,
                    [seed],
                    pages=topic_pages,
                    limit=topic_limit,
                    min_subscribers=min_subscribers,
                    sort=sort_mode,
                )
                if not group:
                    print(f"  «{seed}» — хаб не найден, оставляю как есть")
                    fallbacks.append(seed.strip())
                    continue
                top = group[0]
                print(f"  «{seed}» → {top.title} [{top.slug}]")
                if top.slug in seen_slugs:
                    continue
                seen_slugs.add(top.slug)
                chosen.append(top)
            if fallbacks:
                search_topics = fallbacks
        else:
            available = _fetch_official_topics(
                api,
                seeds,
                pages=topic_pages,
                limit=topic_limit,
                min_subscribers=min_subscribers,
                sort=sort_mode,
            )
            if not available:
                print(
                    "Официальные хабы не нашлись, ищу по исходному запросу: "
                    + ", ".join(seeds)
                )
                search_topics = [seed.strip() for seed in seeds if seed.strip()]
            else:
                prompt_query = seeds[0] if len(seeds) == 1 else ", ".join(seeds)
                try:
                    chosen = select_official_topics(
                        available,
                        pick=pick,
                        slugs=slugs,
                        interactive=interactive and pick is None and not slugs,
                        prompt_query=prompt_query,
                    )
                except ValueError as exc:
                    raise SystemExit(str(exc)) from exc
        if chosen:
            search_topics = [topic.title for topic in chosen] + [
                item for item in search_topics if item not in {topic.title for topic in chosen}
            ]
            print("Смотрим официальные темы:")
            for topic in chosen:
                print(f"  • {topic.title}  [{topic.slug}]  {topic.url}")
        elif not search_topics:
            search_topics = [seed.strip() for seed in seeds if seed.strip()]

    if not search_topics:
        raise SystemExit("Не выбрана ни одна тема для сбора.")

    config = CollectConfig(
        topics=search_topics,
        pages=args.pages if args.pages is not None else int(cfg.get("pages", 2)),
        delay_seconds=delay,
        min_views=args.min_views if args.min_views is not None else int(cfg.get("min_views", 0)),
        top_n=args.top_n if args.top_n is not None else int(cfg.get("top_n", 40)),
        fetch_content=False if args.no_content else bool(cfg.get("fetch_content", True)),
        download_images=False if args.no_images else bool(cfg.get("download_images", True)),
        recirc=False
        if args.no_recirc or channel_only
        else bool(cfg.get("recirc", True)),
        include_feed=False
        if args.no_feed or channel_only
        else bool(cfg.get("include_feed", True)),
        recirc_seeds=(
            args.recirc_seeds
            if args.recirc_seeds is not None
            else int(cfg.get("recirc_seeds", 5))
        ),
        out_dir=args.out_dir,
        seed_items=seed_items,
        channel_only=channel_only,
        portable_html=portable_html,
    )
    paths = collect(config)
    print(f"Собрано материалов: {paths['count']}")
    print(f"CSV и SQLite: {paths['csv']} · {paths['db']}")
    if paths.get("html"):
        print(f"HTML-таблица: {paths['html']}")
        print(f"Откройте в браузере: {paths['html']}")
    print(f"Картинки: {paths['images']}")
    store = ItemStore(paths["db"])
    try:
        rows = store.all_items()
        print(f"Строк в таблице: {len(rows)}")
        _print_table(rows, limit=20)
    finally:
        store.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="viraldzen",
        description="Сбор вирусных материалов Дзена без браузера. Тема словами или ссылка: канал, статья, хаб.",
    )
    parser.add_argument("--version", action="version", version=f"ViralDzen {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    topics_p = sub.add_parser("topics", help="Показать официальные темы Дзена, чтобы выбрать куда смотреть")
    topics_p.add_argument("--query", "-q", help="Запрос, например: здоровье")
    topics_p.add_argument("--pages", type=int, default=1, help="Страниц поиска официальных тем")
    topics_p.add_argument("--limit", type=int, default=20, help="Сколько тем показать")
    topics_p.add_argument("--min-subscribers", type=int, default=0)
    topics_p.add_argument(
        "--sort",
        choices=("search", "subscribers"),
        default="search",
        help="search — порядок Дзена, subscribers — по подписчикам",
    )
    topics_p.add_argument("--delay", type=float, dest="delay_seconds", default=0.7)
    topics_p.add_argument("--json", action="store_true", help="Печать JSON")

    channel_p = sub.add_parser(
        "channel",
        help="Разобрать ссылку Дзена: канал, статью или официальную тему",
    )
    channel_p.add_argument("--url", "-u", required=True, help="Ссылка: канал, статья или dzen.ru/topic/…")
    channel_p.add_argument("--pages", type=int, default=2, help="Страниц ленты канала")
    channel_p.add_argument(
        "--enrich",
        type=int,
        default=8,
        help="Сколько статей открыть, чтобы вытащить теги",
    )
    channel_p.add_argument("--phrase-limit", type=int, default=8, dest="phrase_limit")
    channel_p.add_argument("--limit", type=int, default=15, help="Сколько хабов показать")
    channel_p.add_argument("--delay", type=float, dest="delay_seconds", default=0.7)
    channel_p.add_argument("--json", action="store_true")

    collect_p = sub.add_parser("collect", help="Выбрать официальную тему или канал и собрать вирусные материалы")
    collect_p.add_argument("--topic", action="append", dest="topics", help="Запрос, по которому показать официальные темы")
    collect_p.add_argument("--config", type=Path, help="JSON config (see topics.example.json)")
    collect_p.add_argument("--pick", help="Номер официальной темы из списка, например 1 или 1,3")
    collect_p.add_argument("--slug", action="append", dest="slugs", help="Slug официальной темы, например zdorove")
    collect_p.add_argument("--channel", help="Ссылка на канал: разобрать темы и собрать вирусное по ним")
    collect_p.add_argument(
        "--url",
        help="Любая ссылка Дзена: канал, статья dzen.ru/a/… или хаб dzen.ru/topic/…",
    )
    collect_p.add_argument(
        "--channel-only",
        action="store_true",
        help="Собрать вирусное с ленты этого канала, не искать по всему Дзену",
    )
    collect_p.add_argument(
        "--portable",
        action="store_true",
        help="HTML одним файлом: картинки по URL Дзена, можно скачать без папки images",
    )
    collect_p.add_argument(
        "--channel-limit",
        type=int,
        dest="channel_limit",
        help="Сколько выведенных хабов собирать (по умолчанию 3)",
    )
    collect_p.add_argument("--raw-topic", action="store_true", help="Искать по --topic как есть, не спрашивать официальные хабы")
    collect_p.add_argument("--topic-pages", type=int, help="Страниц поиска официальных тем")
    collect_p.add_argument("--topic-limit", type=int, help="Сколько официальных тем показать")
    collect_p.add_argument("--min-subscribers", type=int)
    collect_p.add_argument(
        "--topic-sort",
        choices=("search", "subscribers"),
        default=None,
        help="Как сортировать список официальных тем",
    )
    collect_p.add_argument("--pages", type=int, help="Search pages per topic")
    collect_p.add_argument("--top", type=int, dest="top_n", help="How many items to keep after scoring")
    collect_p.add_argument("--min-views", type=int, dest="min_views")
    collect_p.add_argument("--out-dir", type=Path, default=Path("data"))
    collect_p.add_argument("--delay", type=float, dest="delay_seconds")
    collect_p.add_argument("--no-content", action="store_true", help="Do not fetch full article text")
    collect_p.add_argument("--no-images", action="store_true", help="Do not download images")
    collect_p.add_argument("--no-recirc", action="store_true", help="Skip related-offer hop")
    collect_p.add_argument("--no-feed", action="store_true", help="Skip Dzen recommendation feed")
    collect_p.add_argument("--recirc-seeds", type=int, dest="recirc_seeds", help="How many seed articles to expand")

    export_p = sub.add_parser("export", help="Export SQLite table to CSV")
    export_p.add_argument("--db", type=Path, default=Path("data/viral.sqlite"))
    export_p.add_argument("--csv", type=Path, default=Path("data/viral.csv"))

    table_p = sub.add_parser("table", help="Print the stored table")
    table_p.add_argument("--db", type=Path, default=Path("data/viral.sqlite"))
    table_p.add_argument("--limit", type=int, default=30)

    html_p = sub.add_parser("html", help="Собрать наглядную HTML-таблицу, которую можно открыть в браузере")
    html_p.add_argument(
        "--db",
        action="append",
        dest="dbs",
        type=Path,
        required=True,
        help="SQLite выгрузка, можно несколько",
    )
    html_p.add_argument("--out", type=Path, help="Куда записать HTML")
    html_p.add_argument("--title", default="Вирусный Дзен")
    html_p.add_argument(
        "--portable",
        action="store_true",
        help="Один файл: картинки по URL Дзена, можно скачать и открыть без папки images",
    )

    args = parser.parse_args(argv)

    if args.command == "topics":
        return _cmd_topics(args)

    if args.command == "channel":
        return _cmd_channel(args)

    if args.command == "collect":
        return _cmd_collect(args)

    if args.command == "export":
        store = ItemStore(args.db)
        try:
            n = store.export_csv(args.csv)
        finally:
            store.close()
        print(f"Exported {n} rows to {args.csv}")
        return 0

    if args.command == "table":
        if not args.db.exists():
            raise SystemExit(f"Database not found: {args.db}")
        store = ItemStore(args.db)
        try:
            rows = store.all_items()
        finally:
            store.close()
        print(f"{len(rows)} rows")
        _print_table(rows, limit=args.limit)
        return 0

    if args.command == "html":
        groups = []
        for db in args.dbs:
            if not db.exists():
                raise SystemExit(f"Database not found: {db}")
            store = ItemStore(db)
            try:
                groups.append(store.all_items())
            finally:
                store.close()
        rows = merge_rows(groups)
        out = args.out or args.dbs[0].parent / "viral.html"
        path = export_html(rows, out, title=args.title, portable=bool(args.portable))
        print(f"HTML table: {path} ({len(rows)} rows)")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
