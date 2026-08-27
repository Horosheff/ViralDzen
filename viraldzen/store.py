from __future__ import annotations

import csv
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from viraldzen.models import ViralItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS viral_items (
    publication_id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    topic TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    snippet TEXT,
    full_text TEXT,
    published_at TEXT,
    collected_at TEXT NOT NULL,
    channel_name TEXT,
    channel_url TEXT,
    channel_id TEXT,
    channel_subscribers INTEGER,
    views INTEGER DEFAULT 0,
    views_till_end INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    time_to_read_seconds INTEGER,
    viral_score REAL DEFAULT 0,
    is_viral INTEGER DEFAULT 0,
    read_through REAL DEFAULT 0,
    engagement_rate REAL DEFAULT 0,
    cover_image_url TEXT,
    cover_image_path TEXT,
    image_urls TEXT,
    image_paths TEXT,
    recirc_parent_url TEXT,
    item_type TEXT,
    tags TEXT
);
"""

UPSERT = """
INSERT INTO viral_items (
    publication_id, url, title, topic, source_kind, snippet, full_text,
    published_at, collected_at, channel_name, channel_url, channel_id,
    channel_subscribers, views, views_till_end, likes, comments,
    time_to_read_seconds, viral_score, is_viral, read_through, engagement_rate,
    cover_image_url, cover_image_path, image_urls, image_paths,
    recirc_parent_url, item_type, tags
) VALUES (
    :publication_id, :url, :title, :topic, :source_kind, :snippet, :full_text,
    :published_at, :collected_at, :channel_name, :channel_url, :channel_id,
    :channel_subscribers, :views, :views_till_end, :likes, :comments,
    :time_to_read_seconds, :viral_score, :is_viral, :read_through, :engagement_rate,
    :cover_image_url, :cover_image_path, :image_urls, :image_paths,
    :recirc_parent_url, :item_type, :tags
)
ON CONFLICT(publication_id) DO UPDATE SET
    title=excluded.title,
    topic=CASE WHEN excluded.topic != '' THEN excluded.topic ELSE viral_items.topic END,
    source_kind=excluded.source_kind,
    snippet=CASE WHEN length(excluded.snippet) >= length(viral_items.snippet) THEN excluded.snippet ELSE viral_items.snippet END,
    full_text=CASE WHEN length(excluded.full_text) >= length(viral_items.full_text) THEN excluded.full_text ELSE viral_items.full_text END,
    published_at=COALESCE(excluded.published_at, viral_items.published_at),
    collected_at=excluded.collected_at,
    channel_name=COALESCE(NULLIF(excluded.channel_name, ''), viral_items.channel_name),
    channel_url=COALESCE(NULLIF(excluded.channel_url, ''), viral_items.channel_url),
    channel_id=COALESCE(NULLIF(excluded.channel_id, ''), viral_items.channel_id),
    channel_subscribers=COALESCE(excluded.channel_subscribers, viral_items.channel_subscribers),
    views=MAX(excluded.views, viral_items.views),
    views_till_end=MAX(excluded.views_till_end, viral_items.views_till_end),
    likes=MAX(excluded.likes, viral_items.likes),
    comments=MAX(excluded.comments, viral_items.comments),
    time_to_read_seconds=COALESCE(excluded.time_to_read_seconds, viral_items.time_to_read_seconds),
    viral_score=excluded.viral_score,
    is_viral=excluded.is_viral,
    read_through=excluded.read_through,
    engagement_rate=excluded.engagement_rate,
    cover_image_url=COALESCE(NULLIF(excluded.cover_image_url, ''), viral_items.cover_image_url),
    cover_image_path=COALESCE(NULLIF(excluded.cover_image_path, ''), viral_items.cover_image_path),
    image_urls=CASE WHEN length(excluded.image_urls) >= length(viral_items.image_urls) THEN excluded.image_urls ELSE viral_items.image_urls END,
    image_paths=CASE WHEN length(excluded.image_paths) >= length(viral_items.image_paths) THEN excluded.image_paths ELSE viral_items.image_paths END,
    recirc_parent_url=COALESCE(NULLIF(excluded.recirc_parent_url, ''), viral_items.recirc_parent_url),
    item_type=COALESCE(NULLIF(excluded.item_type, ''), viral_items.item_type),
    tags=CASE WHEN length(excluded.tags) >= length(viral_items.tags) THEN excluded.tags ELSE viral_items.tags END
"""

CSV_FIELDS = [
    "publication_id",
    "url",
    "title",
    "topic",
    "source_kind",
    "published_at",
    "collected_at",
    "channel_name",
    "channel_url",
    "views",
    "views_till_end",
    "likes",
    "comments",
    "read_through",
    "engagement_rate",
    "viral_score",
    "is_viral",
    "time_to_read_seconds",
    "cover_image_url",
    "cover_image_path",
    "image_urls",
    "image_paths",
    "snippet",
    "full_text",
    "recirc_parent_url",
    "item_type",
    "tags",
]


class ItemStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def upsert(self, item: ViralItem) -> None:
        if not item.collected_at:
            item.collected_at = datetime.now(timezone.utc).isoformat()
        self.conn.execute(UPSERT, item.to_row())
        self.conn.commit()

    def upsert_many(self, items: Iterable[ViralItem]) -> int:
        count = 0
        for item in items:
            self.upsert(item)
            count += 1
        return count

    def all_items(self) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT * FROM viral_items ORDER BY is_viral DESC, viral_score DESC, views DESC"
        )
        return list(cur.fetchall())

    def export_csv(self, csv_path: str | Path) -> int:
        rows = self.all_items()
        path = Path(csv_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row[field] for field in CSV_FIELDS})
        return len(rows)
