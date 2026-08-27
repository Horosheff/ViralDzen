from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def unix_to_iso(value: Any) -> str | None:
    if value in (None, "", 0, "0"):
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        return str(value)
    if ts > 10_000_000_000:
        ts /= 1000.0
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return str(value)


@dataclass
class OfficialTopic:
    """Official Dzen topic hub (dzen.ru/topic/<slug>)."""

    topic_id: str
    slug: str
    title: str
    subscribers: int
    url: str
    logo_url: str = ""
    query: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.topic_id,
            "slug": self.slug,
            "title": self.title,
            "subscribers": self.subscribers,
            "url": self.url,
            "logo_url": self.logo_url,
        }


@dataclass
class ViralItem:
    publication_id: str
    url: str
    title: str
    topic: str
    source_kind: str
    snippet: str = ""
    full_text: str = ""
    published_at: str | None = None
    collected_at: str = ""
    channel_name: str = ""
    channel_url: str = ""
    channel_id: str = ""
    channel_subscribers: int | None = None
    views: int = 0
    views_till_end: int = 0
    likes: int = 0
    comments: int = 0
    time_to_read_seconds: int | None = None
    viral_score: float = 0.0
    is_viral: bool = False
    read_through: float = 0.0
    engagement_rate: float = 0.0
    cover_image_url: str = ""
    cover_image_path: str = ""
    image_urls: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    recirc_parent_url: str = ""
    item_type: str = "article"
    tags: list[str] = field(default_factory=list)

    def to_row(self) -> dict[str, Any]:
        row = asdict(self)
        row["image_urls"] = " | ".join(self.image_urls)
        row["image_paths"] = " | ".join(self.image_paths)
        row["tags"] = " | ".join(self.tags)
        row["is_viral"] = int(self.is_viral)
        return row
