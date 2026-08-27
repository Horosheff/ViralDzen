from __future__ import annotations

import json
import unittest

from viraldzen.models import ViralItem
from viraldzen.parse import (
    canonical_article_url,
    draftjs_text_and_images,
    extra_search_queries,
    image_url_from_obj,
    is_clickbait,
    iter_feed_items,
    matches_topic,
    next_search_link,
    normalize_card,
    parse_article_ssr,
    publication_id_from_url,
)


class ParseTests(unittest.TestCase):
    def test_canonical_and_id(self) -> None:
        url = "https://dzen.ru/a/abcDEF123?from=feed&clid=1400"
        self.assertEqual(canonical_article_url(url), "https://dzen.ru/a/abcDEF123")
        self.assertEqual(publication_id_from_url(url), "abcDEF123")

    def test_image_template(self) -> None:
        url = image_url_from_obj(
            {
                "urlTemplate": "https://avatars.dzeninfra.ru/get-{namespace}/271828/pub_1/{size}",
                "namespace": "zen_doc",
            }
        )
        self.assertEqual(
            url,
            "https://avatars.dzeninfra.ru/get-zen_doc/271828/pub_1/scale_1200",
        )

    def test_normalize_search_card(self) -> None:
        raw = {
            "type": "article",
            "id": "pub1",
            "title": "Здоровье кишечника: связь с организмом",
            "text": "Короткий сниппет про здоровье",
            "shareLink": "https://dzen.ru/a/abc123",
            "views": 15000,
            "viewsTillEnd": 6000,
            "publicationDate": 1727371497,
            "socialInfo": {"likesCount": 80, "commentCount": 12},
            "source": {"title": "Канал", "shareLink": "https://dzen.ru/healthblog", "id": "id1"},
            "tags": [{"name": "здоровье"}, "кишечник"],
            "image": {
                "urlTemplate": "https://avatars.dzeninfra.ru/get-{namespace}/1/cover/{size}",
                "namespace": "zen_doc",
            },
        }
        item = normalize_card(raw, topic="здоровье", source_kind="search")
        assert item is not None
        self.assertEqual(item.title.startswith("Здоровье"), True)
        self.assertEqual(item.views, 15000)
        self.assertEqual(item.likes, 80)
        self.assertTrue(item.cover_image_url.endswith("/scale_1200"))
        self.assertEqual(item.published_at is not None, True)
        self.assertEqual(item.tags, ["здоровье", "кишечник"])

    def test_skip_ads_and_video(self) -> None:
        self.assertIsNone(normalize_card({"type": "hidden", "title": "x"}, "t", "search"))
        video = {
            "type": "article",
            "title": "Ролик",
            "shareLink": "https://dzen.ru/video/watch/abc",
        }
        self.assertIsNone(normalize_card(video, "t", "search"))

    def test_iter_feed_and_more(self) -> None:
        payload = {
            "feedData": {
                "items": [
                    {"type": "article", "title": "A", "shareLink": "https://dzen.ru/a/1"},
                    {"type": "hidden"},
                ],
                "more": {"link": "https://dzen.ru/api/web/v1/zen-search?query=next"},
            }
        }
        items = iter_feed_items(payload)
        self.assertEqual(len(items), 2)
        self.assertIn("zen-search", next_search_link(payload) or "")

    def test_draftjs_text(self) -> None:
        state = {
            "draftJsState": {
                "blocks": [
                    {"type": "header-two", "text": "Заголовок секции"},
                    {"type": "unstyled", "text": "Первый абзац."},
                    {
                        "type": "atomic:image",
                        "text": "",
                        "data": {"image": {"id": "img1"}},
                    },
                    {"type": "unordered-list-item", "text": "пункт"},
                ],
                "entityMap": {},
            }
        }
        text, image_ids = draftjs_text_and_images(state)
        self.assertIn("Первый абзац.", text)
        self.assertIn("• пункт", text)
        self.assertEqual(image_ids, ["img1"])

    def test_parse_article_ssr(self) -> None:
        ssr = {
            "publishersResponse": {
                "data": {
                    "title": "Большой заголовок",
                    "data": {
                        "publisher": {"id": "pubid", "name": "Автор", "nickname": "author"},
                        "publisherSubscribersCount": {"subscribersCount": 1200},
                        "images": {
                            "img1": {
                                "id": "img1",
                                "namespace": "zen_doc",
                                "groupId": 271828,
                                "imageName": "pub_x_img1",
                            }
                        },
                        "publication": {
                            "id": "hexid",
                            "publishTime": 1727371497000,
                            "itemType": "native",
                            "publicationStatistics": {"views": 9000, "viewsTillEnd": 3000},
                            "content": {
                                "type": "article",
                                "timeToReadSeconds": 90,
                                "preview": {
                                    "title": "Большой заголовок",
                                    "snippet": "сниппет",
                                    "image": {
                                        "id": "img1",
                                        "namespace": "zen_doc",
                                        "groupId": 271828,
                                        "imageName": "pub_x_img1",
                                    },
                                },
                                "articleContent": {
                                    "contentState": json.dumps(
                                        {
                                            "draftJsState": {
                                                "blocks": [
                                                    {"type": "unstyled", "text": "Полный текст статьи."}
                                                ],
                                                "entityMap": {},
                                            }
                                        }
                                    )
                                },
                            },
                        },
                    },
                }
            },
            "socialMetaResponse": {
                "items": [{"metaInfo": {"likeCount": 10, "commentsCount": 3}}]
            },
        }
        item = parse_article_ssr(ssr, "https://dzen.ru/a/hexid?x=1", "здоровье")
        assert item is not None
        self.assertEqual(item.full_text, "Полный текст статьи.")
        self.assertEqual(item.views, 9000)
        self.assertEqual(item.likes, 10)
        self.assertTrue(item.cover_image_url.startswith("https://avatars.dzeninfra.ru/"))
        self.assertEqual(item.channel_name, "Автор")

    def test_topic_match(self) -> None:
        item = ViralItem(
            publication_id="1",
            url="https://dzen.ru/a/1",
            title="Как сохранить здоровье суставов",
            topic="",
            source_kind="feed",
            snippet="",
        )
        self.assertTrue(matches_topic(item, "здоровье"))
        self.assertTrue(matches_topic(item, "Здоровье и медицина"))
        genitive = ViralItem(
            publication_id="1b",
            url="https://dzen.ru/a/1b",
            title="Обследования для твоего здоровья",
            topic="",
            source_kind="search",
            snippet="",
        )
        self.assertTrue(matches_topic(genitive, "здоровье"))
        self.assertFalse(matches_topic(item, "криптобиржа"))
        healthy_false_friend = ViralItem(
            publication_id="1c",
            url="https://dzen.ru/a/1c",
            title="Это было просто здорово",
            topic="",
            source_kind="feed",
            snippet="",
        )
        self.assertFalse(matches_topic(healthy_false_friend, "здоровье"))
        off = ViralItem(
            publication_id="2",
            url="https://dzen.ru/a/2",
            title="Какой будет первая тиара принцессы Шарлотты?",
            topic="здоровье",
            source_kind="feed",
            snippet="Королевский выход",
        )
        self.assertFalse(matches_topic(off, "здоровье"))

    def test_clickbait_and_extra_queries(self) -> None:
        self.assertTrue(is_clickbait("Вы в числе 10% умников, если сможете ответить на 8/10"))
        self.assertFalse(is_clickbait("Здоровье кишечника: связь с организмом"))
        queries = extra_search_queries("здоровье", "Здоровье кишечника: связь с организмом")
        self.assertTrue(any("кишечника" in q for q in queries))


if __name__ == "__main__":
    unittest.main()
