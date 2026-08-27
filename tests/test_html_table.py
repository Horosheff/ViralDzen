from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from viraldzen.cli import main
from viraldzen.html_table import export_html, format_int, merge_rows
from viraldzen.models import ViralItem
from viraldzen.store import ItemStore


class HtmlTableTests(unittest.TestCase):
    def test_format_int_uses_spaces(self) -> None:
        self.assertEqual(format_int(13867), "13 867")

    def test_merge_keeps_higher_views(self) -> None:
        low = {"publication_id": "a", "views": 10, "viral_score": 1, "is_viral": 0}
        high = {"publication_id": "a", "views": 50, "viral_score": 2, "is_viral": 1}
        merged = merge_rows([[low], [high]])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["views"], 50)

    def test_export_html_escapes_and_links_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cover = root / "images" / "cover.jpg"
            cover.parent.mkdir()
            cover.write_bytes(b"jpeg")
            html_path = root / "viral.html"
            rows = [
                {
                    "publication_id": "abc",
                    "url": "https://dzen.ru/a/abc",
                    "title": "<script>alert(1)</script> Заголовок",
                    "topic": "спорт",
                    "source_kind": "search",
                    "snippet": "короткий текст",
                    "full_text": "полный текст статьи",
                    "published_at": "2026-08-01T00:00:00+00:00",
                    "channel_name": "Канал",
                    "channel_url": "https://dzen.ru/channel",
                    "views": 13867,
                    "likes": 15,
                    "comments": 2,
                    "viral_score": 7.49,
                    "is_viral": 1,
                    "cover_image_path": str(cover),
                    "cover_image_url": "https://example.com/cover.jpg",
                    "image_paths": str(cover),
                    "image_urls": "https://example.com/cover.jpg",
                }
            ]
            export_html(rows, html_path, title="Проверка")
            text = html_path.read_text(encoding="utf-8")
            self.assertIn("Проверка", text)
            self.assertIn("&lt;script&gt;", text)
            self.assertNotIn("<script>alert(1)</script>", text)
            self.assertIn("13 867", text)
            self.assertIn("спорт", text)
            self.assertIn("images/cover.jpg", text)
            self.assertIn("полный текст статьи", text)
            self.assertIn("dataset.topic === startTopic", text)
            self.assertNotIn('data-topic="" +', text)

    def test_portable_html_uses_remote_images(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            html_path = Path(tmp) / "portable.html"
            rows = [
                {
                    "publication_id": "abc",
                    "url": "https://dzen.ru/a/abc",
                    "title": "Портативный",
                    "topic": "здоровье",
                    "views": 10,
                    "likes": 1,
                    "comments": 0,
                    "viral_score": 1.0,
                    "is_viral": 0,
                    "cover_image_path": "/no/such/local.jpg",
                    "cover_image_url": "https://avatars.dzeninfra.ru/cover.jpg",
                    "image_urls": "https://avatars.dzeninfra.ru/one.jpg",
                    "published_at": "2026-08-01T00:00:00+00:00",
                }
            ]
            export_html(rows, html_path, portable=True)
            text = html_path.read_text(encoding="utf-8")
            self.assertIn("https://avatars.dzeninfra.ru/cover.jpg", text)
            self.assertNotIn("/no/such/local.jpg", text)

    def test_html_cli_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "viral.sqlite"
            out = Path(tmp) / "table.html"
            store = ItemStore(db)
            store.upsert(
                ViralItem(
                    publication_id="x",
                    url="https://dzen.ru/a/x",
                    title="Тема HTML",
                    topic="здоровье",
                    source_kind="search",
                    views=100,
                )
            )
            store.close()
            code = main(["html", "--db", str(db), "--out", str(out), "--title", "Доска"])
            self.assertEqual(code, 0)
            text = out.read_text(encoding="utf-8")
            self.assertIn("Доска", text)
            self.assertIn("Тема HTML", text)
            self.assertIn("здоровье", text)


if __name__ == "__main__":
    unittest.main()
