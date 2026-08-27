from __future__ import annotations

import math
from datetime import datetime, timezone

from viraldzen.models import ViralItem
from viraldzen.parse import is_clickbait


def _age_hours(published_at: str | None, now: datetime) -> float | None:
    if not published_at:
        return None
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    delta = (now - published).total_seconds() / 3600.0
    return max(delta, 0.01)


def score_item(item: ViralItem, now: datetime | None = None) -> ViralItem:
    now = now or datetime.now(timezone.utc)
    views = max(item.views, 0)
    likes = max(item.likes, 0)
    comments = max(item.comments, 0)
    read_through = 0.0
    if views > 0 and item.views_till_end > 0:
        read_through = min(item.views_till_end / views, 1.0)
    engagement = ((likes + comments) / views) if views > 0 else 0.0
    age_hours = _age_hours(item.published_at, now)
    velocity = 0.0
    if age_hours is not None:
        velocity = math.log1p(views / max(age_hours, 1.0))
    trusted_er = min(engagement, 0.05) if views >= 300 else 0.0
    score = (
        0.55 * math.log1p(views)
        + 0.15 * math.log1p(likes)
        + 0.10 * math.log1p(comments)
        + 0.12 * (read_through * 8.0)
        + 0.08 * velocity
        + 1.5 * math.log1p(trusted_er * 100.0)
    )
    if item.source_kind == "search":
        score += 1.2
    if is_clickbait(item.title):
        score *= 0.35
    if views == 0:
        score *= 0.25
    item.read_through = round(read_through, 4)
    item.engagement_rate = round(engagement, 6)
    item.viral_score = round(score, 4)
    return item


def mark_viral(items: list[ViralItem], min_views: int = 0) -> list[ViralItem]:
    if not items:
        return items
    scored = [score_item(item) for item in items]
    scores = sorted(item.viral_score for item in scored)
    q75 = scores[int(0.75 * (len(scores) - 1))] if scores else 0.0
    median_views = sorted(item.views for item in scored)[len(scored) // 2]
    for item in scored:
        high_views = item.views >= max(min_views, 10_000, median_views * 3 if median_views else 10_000)
        high_score = item.viral_score >= q75 and item.views >= max(min_views, 300)
        high_er = item.engagement_rate >= 0.02 and item.views >= max(min_views, 1000)
        strong_read = item.read_through >= 0.35 and item.views >= max(min_views, 2000)
        item.is_viral = bool(high_views or high_score or high_er or strong_read)
    scored.sort(key=lambda item: (item.is_viral, item.viral_score, item.views), reverse=True)
    return scored
