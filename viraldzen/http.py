from __future__ import annotations

import json
import random
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


class DzenHttpError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, url: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.url = url


class DzenClient:
    """HTTP client for public Dzen JSON/HTML endpoints. No browser."""

    def __init__(
        self,
        cookie_path: str | Path | None = None,
        delay_seconds: float = 0.7,
        timeout: int = 30,
        retries: int = 3,
    ) -> None:
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.retries = retries
        self.cookie_path = Path(cookie_path) if cookie_path else None
        self.cookie_jar = MozillaCookieJar()
        if self.cookie_path and self.cookie_path.exists():
            try:
                self.cookie_jar.load(str(self.cookie_path), ignore_discard=True, ignore_expires=True)
            except OSError:
                pass
        ctx = ssl.create_default_context()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPSHandler(context=ctx),
        )
        self._last_request_at = 0.0

    def save_cookies(self) -> None:
        if not self.cookie_path:
            return
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        self.cookie_jar.save(str(self.cookie_path), ignore_discard=True, ignore_expires=True)

    def _throttle(self) -> None:
        if self.delay_seconds <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self.delay_seconds + random.uniform(0, self.delay_seconds * 0.3)
        if elapsed < wait:
            time.sleep(wait - elapsed)

    def request(self, url: str, accept: str | None = None) -> tuple[int, str, bytes]:
        headers = dict(DEFAULT_HEADERS)
        if accept:
            headers["Accept"] = accept
        last_error: Exception | None = None
        for attempt in range(self.retries):
            self._throttle()
            req = urllib.request.Request(url, headers=headers, method="GET")
            try:
                with self._opener.open(req, timeout=self.timeout) as resp:
                    body = resp.read()
                    status = getattr(resp, "status", 200)
                    ctype = resp.headers.get("Content-Type", "")
                    self._last_request_at = time.monotonic()
                    self.save_cookies()
                    return status, ctype, body
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.fp:
                    exc.read()
                if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < self.retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                self._last_request_at = time.monotonic()
                raise DzenHttpError(
                    f"HTTP {exc.code} for {url}", status=exc.code, url=url
                ) from exc
            except urllib.error.URLError as exc:
                last_error = exc
                if attempt + 1 < self.retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise DzenHttpError(f"Network error for {url}: {exc}", url=url) from exc
        raise DzenHttpError(f"Request failed for {url}: {last_error}", url=url)

    def get_text(self, url: str, accept: str | None = None) -> str:
        _status, _ctype, body = self.request(url, accept=accept)
        return body.decode("utf-8", errors="replace")

    def get_json(self, url: str) -> Any:
        text = self.get_text(url, accept="application/json")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise DzenHttpError(f"Invalid JSON from {url}", url=url) from exc

    def get_bytes(self, url: str) -> bytes:
        _status, _ctype, body = self.request(url)
        return body

    def warmup(self) -> None:
        """Hit a public JSON endpoint so Dzen cookies exist before HTML pages."""
        url = "https://dzen.ru/api/v3/launcher/export?country_code=ru&clid=1400&lang=ru"
        try:
            self.get_json(url)
        except DzenHttpError:
            pass


def build_url(base: str, params: dict[str, Any]) -> str:
    cleaned = {k: v for k, v in params.items() if v is not None}
    return base + "?" + urllib.parse.urlencode(cleaned, safe=",")
