from __future__ import annotations

import io
import unittest

from viraldzen.models import OfficialTopic
from viraldzen.parse import parse_official_topic, slug_from_topic_url
from viraldzen.topics import (
    apply_topic_filters,
    format_official_topics,
    merge_official_topics,
    parse_selection,
    select_official_topics,
)


def _topic(
    slug: str,
    title: str,
    subscribers: int,
    topic_id: str | None = None,
) -> OfficialTopic:
    return OfficialTopic(
        topic_id=topic_id or slug,
        slug=slug,
        title=title,
        subscribers=subscribers,
        url=f"https://dzen.ru/topic/{slug}",
    )


class OfficialTopicParseTests(unittest.TestCase):
    def test_slug_from_topic_url(self) -> None:
        self.assertEqual(slug_from_topic_url("https://dzen.ru/topic/zdorove?clid=1400"), "zdorove")
        self.assertEqual(slug_from_topic_url("/topic/politika"), "politika")
        self.assertEqual(slug_from_topic_url("https://dzen.ru/kizru"), "")

    def test_parse_camel_case_card(self) -> None:
        raw = {
            "id": "14888",
            "type": "search_topic_channel_card",
            "itemType": "search_topic_channel_card",
            "topicChannelInfo": {
                "id": "14888",
                "strongestId": "topic_channel:14888",
                "title": "Здоровье и медицина",
                "subscribers": 3970600,
                "logo": "https://avatars.dzeninfra.ru/get-zen-logos/271828/zdorove/xxh",
                "feedLink": "https://dzen.ru/topic/zdorove",
            },
        }
        topic = parse_official_topic(raw, query="здоровье")
        assert topic is not None
        self.assertEqual(topic.slug, "zdorove")
        self.assertEqual(topic.topic_id, "14888")
        self.assertEqual(topic.title, "Здоровье и медицина")
        self.assertEqual(topic.subscribers, 3970600)
        self.assertEqual(topic.url, "https://dzen.ru/topic/zdorove")
        self.assertEqual(topic.query, "здоровье")

    def test_parse_snake_case_card(self) -> None:
        raw = {
            "type": "search_topic_channel_card",
            "item_type": "search_topic_channel_card",
            "topic_channel_info": {
                "id": "1",
                "title": "Спорт",
                "formatted_subscribers": "9.3M",
                "feed_link": "https://dzen.ru/topic/sport",
            },
        }
        topic = parse_official_topic(raw)
        assert topic is not None
        self.assertEqual(topic.slug, "sport")
        self.assertEqual(topic.subscribers, 9_300_000)

    def test_skip_non_topic_cards(self) -> None:
        self.assertIsNone(parse_official_topic({"type": "native", "title": "Статья"}))
        self.assertIsNone(
            parse_official_topic(
                {
                    "type": "search_topic_channel_card",
                    "topicChannelInfo": {"title": "Без ссылки"},
                }
            )
        )


class OfficialTopicSelectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.topics = [
            _topic("zdorove", "Здоровье и медицина", 3_970_600, "14888"),
            _topic("zdorovje-spiny-i-shei", "Здоровье спины и шеи", 195_335),
            _topic("pravilnoe-pitanie", "Правильное питание", 87_552),
        ]

    def test_parse_number_and_slug_and_all(self) -> None:
        self.assertEqual(parse_selection("1", self.topics)[0].slug, "zdorove")
        self.assertEqual(
            [topic.slug for topic in parse_selection("1,3", self.topics)],
            ["zdorove", "pravilnoe-pitanie"],
        )
        self.assertEqual(parse_selection("zdorove", self.topics)[0].title, "Здоровье и медицина")
        self.assertEqual(len(parse_selection("все", self.topics)), 3)
        self.assertEqual(parse_selection("topic/zdorove", self.topics)[0].slug, "zdorove")

    def test_parse_title_prefix(self) -> None:
        self.assertEqual(parse_selection("Правильное", self.topics)[0].slug, "pravilnoe-pitanie")

    def test_parse_errors(self) -> None:
        with self.assertRaises(ValueError):
            parse_selection("", self.topics)
        with self.assertRaises(ValueError):
            parse_selection("99", self.topics)
        with self.assertRaises(ValueError):
            parse_selection("нет-такой", self.topics)

    def test_format_contains_columns(self) -> None:
        table = format_official_topics(self.topics)
        self.assertIn("zdorove", table)
        self.assertIn("Здоровье и медицина", table)
        self.assertIn("3 970 600", table)

    def test_sort_and_min_subscribers(self) -> None:
        filtered = apply_topic_filters(
            self.topics,
            min_subscribers=100_000,
            sort="subscribers",
        )
        self.assertEqual([topic.slug for topic in filtered], ["zdorove", "zdorovje-spiny-i-shei"])

    def test_merge_keeps_first_slug(self) -> None:
        extra = [_topic("zdorove", "Дубль", 1)]
        merged = merge_official_topics([self.topics, extra])
        self.assertEqual(merged[0].title, "Здоровье и медицина")
        self.assertEqual(len(merged), 3)

    def test_noninteractive_picks_first(self) -> None:
        buf: list[str] = []
        chosen = select_official_topics(
            self.topics,
            interactive=False,
            prompt_query="здоровье",
            print_fn=buf.append,
        )
        self.assertEqual(chosen[0].slug, "zdorove")
        self.assertTrue(any("Неинтерактивный режим" in line for line in buf))
        self.assertTrue(any("Здоровье и медицина" in line for line in buf))

    def test_pick_and_slug_flags(self) -> None:
        self.assertEqual(
            select_official_topics(self.topics, pick="2", show_list=False)[0].slug,
            "zdorovje-spiny-i-shei",
        )
        self.assertEqual(
            select_official_topics(self.topics, slugs=["pravilnoe-pitanie"], show_list=False)[0].slug,
            "pravilnoe-pitanie",
        )

    def test_interactive_prompt(self) -> None:
        answers = iter(["нет", "2"])
        buf: list[str] = []
        chosen = select_official_topics(
            self.topics,
            interactive=True,
            prompt_query="здоровье",
            input_fn=lambda _msg: next(answers),
            print_fn=buf.append,
        )
        self.assertEqual(chosen[0].slug, "zdorovje-spiny-i-shei")
        self.assertTrue(any("Куда смотреть" in line for line in buf))
        self.assertTrue(any("Не понял выбор" in line for line in buf))

    def test_interactive_stdin(self) -> None:
        chosen = select_official_topics(
            self.topics,
            interactive=True,
            show_list=False,
            stdin=io.StringIO("все\n"),
            print_fn=lambda _line: None,
        )
        self.assertEqual(len(chosen), 3)


class CliTopicsHelpTests(unittest.TestCase):
    def test_topics_command_exists(self) -> None:
        from viraldzen.cli import main

        with self.assertRaises(SystemExit) as caught:
            main(["topics", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
