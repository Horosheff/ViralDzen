from __future__ import annotations

import unittest
from datetime import datetime, timezone

from viraldzen.models import ViralItem
from viraldzen.score import mark_viral, score_item


def _item(**kwargs) -> ViralItem:
    base = dict(
        publication_id="x",
        url="https://dzen.ru/a/x",
        title="t",
        topic="здоровье",
        source_kind="search",
    )
    base.update(kwargs)
    return ViralItem(**base)  # type: ignore[arg-type]


class ScoreTests(unittest.TestCase):
    def test_higher_views_score_higher(self) -> None:
        low = score_item(_item(publication_id="a", url="https://dzen.ru/a/a", views=100, likes=1))
        high = score_item(_item(publication_id="b", url="https://dzen.ru/a/b", views=50_000, likes=400))
        self.assertGreater(high.viral_score, low.viral_score)

    def test_mark_viral_flags_outliers(self) -> None:
        items = [
            _item(publication_id=str(i), url=f"https://dzen.ru/a/{i}", views=200, likes=1)
            for i in range(8)
        ]
        items.append(
            _item(
                publication_id="hit",
                url="https://dzen.ru/a/hit",
                views=80_000,
                views_till_end=30_000,
                likes=900,
                comments=120,
            )
        )
        ranked = mark_viral(items)
        self.assertEqual(ranked[0].publication_id, "hit")
        self.assertTrue(ranked[0].is_viral)

    def test_zero_views_do_not_beat_real_reach(self) -> None:
        popular = score_item(
            _item(
                publication_id="p",
                url="https://dzen.ru/a/p",
                title="Что врачи нашли на плановом осмотре",
                views=7500,
                likes=130,
            )
        )
        empty = score_item(
            _item(
                publication_id="e",
                url="https://dzen.ru/a/e",
                title="Что же такое здоровье?",
                views=0,
                likes=3,
            )
        )
        self.assertGreater(popular.viral_score, empty.viral_score)

    def test_read_through(self) -> None:
        item = score_item(
            _item(views=1000, views_till_end=400),
            now=datetime(2026, 8, 24, tzinfo=timezone.utc),
        )
        self.assertAlmostEqual(item.read_through, 0.4)

    def test_clickbait_is_downranked(self) -> None:
        normal = score_item(
            _item(
                publication_id="n",
                url="https://dzen.ru/a/n",
                title="Здоровье кишечника: связь с организмом",
                source_kind="search",
                views=5000,
                likes=80,
            )
        )
        bait = score_item(
            _item(
                publication_id="b",
                url="https://dzen.ru/a/b",
                title="Вы в числе 10% умников, если сможете ответить на 8/10 вопросов",
                source_kind="recirc",
                views=5000,
                likes=80,
            )
        )
        self.assertGreater(normal.viral_score, bait.viral_score)


if __name__ == "__main__":
    unittest.main()
