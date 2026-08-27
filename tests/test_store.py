from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from viraldzen.models import ViralItem
from viraldzen.store import ItemStore


class StoreTests(unittest.TestCase):
    def test_upsert_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "viral.sqlite"
            csv_path = Path(tmp) / "viral.csv"
            store = ItemStore(db)
            item = ViralItem(
                publication_id="abc",
                url="https://dzen.ru/a/abc",
                title="Заголовок",
                topic="здоровье",
                source_kind="search",
                snippet="сниппет",
                full_text="полный текст",
                published_at="2026-08-01T00:00:00+00:00",
                views=1000,
                likes=10,
                cover_image_url="https://example.com/cover.jpg",
                image_urls=["https://example.com/cover.jpg"],
            )
            store.upsert(item)
            item.full_text = "полный текст ещё длиннее чем был"
            item.views = 1500
            store.upsert(item)
            rows = store.all_items()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["views"], 1500)
            self.assertIn("длиннее", rows[0]["full_text"])
            n = store.export_csv(csv_path)
            store.close()
            self.assertEqual(n, 1)
            text = csv_path.read_text(encoding="utf-8-sig")
            self.assertIn("Заголовок", text)
            self.assertIn("полный текст", text)


if __name__ == "__main__":
    unittest.main()
