from __future__ import annotations

import unittest

from viraldzen.channel import parse_channel_ref, parse_dzen_link, rank_phrases
from viraldzen.cli import main
from viraldzen.models import ViralItem


class ParseChannelRefTests(unittest.TestCase):
    def test_name_from_url(self) -> None:
        ref = parse_channel_ref("https://dzen.ru/healthblog?from=feed")
        self.assertEqual(ref.kind, "name")
        self.assertEqual(ref.value, "healthblog")
        self.assertEqual(ref.export_key, "healthblog")
        self.assertEqual(ref.url, "https://dzen.ru/healthblog")

    def test_id_from_url(self) -> None:
        ref = parse_channel_ref("https://dzen.ru/id/5e123abc/extra")
        self.assertEqual(ref.kind, "id")
        self.assertEqual(ref.value, "5e123abc")
        self.assertEqual(ref.export_key, "id/5e123abc")

    def test_bare_name_and_id(self) -> None:
        self.assertEqual(parse_channel_ref("@healthblog").value, "healthblog")
        self.assertEqual(parse_channel_ref("id/99").kind, "id")
        self.assertEqual(parse_channel_ref("dzen.ru/kizru").value, "kizru")

    def test_rejects_articles_and_topics(self) -> None:
        with self.assertRaises(ValueError):
            parse_channel_ref("https://dzen.ru/a/abcdef")
        with self.assertRaises(ValueError):
            parse_channel_ref("https://dzen.ru/topic/zdorove")
        with self.assertRaises(ValueError):
            parse_channel_ref("")


class ParseDzenLinkTests(unittest.TestCase):
    def test_topic_article_channel(self) -> None:
        topic = parse_dzen_link("https://dzen.ru/topic/zdorove?clid=1400")
        self.assertEqual(topic.kind, "topic")
        self.assertEqual(topic.slug, "zdorove")
        article = parse_dzen_link("https://dzen.ru/a/abcdef123")
        self.assertEqual(article.kind, "article")
        self.assertEqual(article.article_url, "https://dzen.ru/a/abcdef123")
        channel = parse_dzen_link("https://dzen.ru/id/655b1a7e519240465e93f635")
        self.assertEqual(channel.kind, "channel")
        assert channel.channel is not None
        self.assertEqual(channel.channel.export_key, "id/655b1a7e519240465e93f635")
        brief = parse_dzen_link("https://www.dzen.ru/b/abcdef123")
        self.assertEqual(brief.kind, "article")
        self.assertEqual(brief.article_url, "https://dzen.ru/b/abcdef123")
        renamed = parse_dzen_link("https://zen.yandex.ru/kizru")
        self.assertEqual(renamed.kind, "channel")
        assert renamed.channel is not None
        self.assertEqual(renamed.channel.value, "kizru")

    def test_rejects_video(self) -> None:
        with self.assertRaises(ValueError):
            parse_dzen_link("https://dzen.ru/video/watch/abc")
        with self.assertRaises(ValueError):
            parse_dzen_link("https://dzen.ru/shorts/abc")


class RankPhrasesTests(unittest.TestCase):
    def test_tags_outrank_title_noise(self) -> None:
        items = [
            ViralItem(
                publication_id="1",
                url="https://dzen.ru/a/1",
                title="Как это сделать дома вечером",
                topic="",
                source_kind="channel",
                tags=["здоровье", "питание"],
            ),
            ViralItem(
                publication_id="2",
                url="https://dzen.ru/a/2",
                title="Ещё про питание вечером",
                topic="",
                source_kind="channel",
                tags=["питание"],
            ),
        ]
        hints = rank_phrases(items, limit=5)
        phrases = [hint.phrase for hint in hints]
        self.assertIn("питание", phrases)
        self.assertIn("здоровье", phrases)
        self.assertGreater(hints[0].score, 1)
        self.assertNotIn("вечером", phrases[:1])

    def test_bigrams_from_titles(self) -> None:
        items = [
            ViralItem(
                publication_id="1",
                url="https://dzen.ru/a/1",
                title="Женское здоровье каждый день",
                topic="",
                source_kind="channel",
            ),
            ViralItem(
                publication_id="2",
                url="https://dzen.ru/a/2",
                title="Женское здоровье и сон",
                topic="",
                source_kind="channel",
            ),
        ]
        phrases = [hint.phrase.lower() for hint in rank_phrases(items, limit=8)]
        self.assertTrue(any("женское здоровье" == phrase for phrase in phrases))


class CliChannelHelpTests(unittest.TestCase):
    def test_channel_command_exists(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            main(["channel", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
