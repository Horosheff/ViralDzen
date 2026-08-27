from __future__ import annotations

import re
from pathlib import Path

from viraldzen.http import DzenClient, DzenHttpError
from viraldzen.models import ViralItem

_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_id(value: str) -> str:
    cleaned = _SAFE_RE.sub("_", value).strip("_")
    return cleaned[:80] or "item"


def _ext_from_bytes(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG"):
        return ".png"
    if payload.startswith(b"GIF8"):
        return ".gif"
    if payload.startswith(b"RIFF") and b"WEBP" in payload[:16]:
        return ".webp"
    return ".jpg"


def download_images(
    client: DzenClient,
    item: ViralItem,
    images_dir: Path,
    max_images: int = 12,
) -> ViralItem:
    dest_dir = images_dir / safe_id(item.publication_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    cover_path = ""
    urls = []
    if item.cover_image_url:
        urls.append(item.cover_image_url)
    for url in item.image_urls:
        if url not in urls:
            urls.append(url)
    for index, url in enumerate(urls[:max_images]):
        filename = f"{index:02d}{Path(url.split('?')[0]).suffix}"
        if filename == f"{index:02d}" or len(filename) > 8:
            filename = f"{index:02d}.jpg"
        dest = dest_dir / filename
        try:
            payload = client.get_bytes(url)
        except DzenHttpError:
            continue
        if len(payload) < 64:
            continue
        ext = _ext_from_bytes(payload)
        dest = dest_dir / f"{index:02d}{ext}"
        dest.write_bytes(payload)
        rel = str(dest)
        paths.append(rel)
        if index == 0:
            cover_path = rel
    if paths:
        item.image_paths = paths
        item.cover_image_path = cover_path or paths[0]
    return item
