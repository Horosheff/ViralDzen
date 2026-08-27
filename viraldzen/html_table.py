from __future__ import annotations

import html
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path

Row = Mapping[str, object]

_MONTHS_RU = (
    "янв",
    "фев",
    "мар",
    "апр",
    "мая",
    "июн",
    "июл",
    "авг",
    "сен",
    "окт",
    "ноя",
    "дек",
)

_CSS = """
:root {
  --paper: #f3eee4;
  --card: #fffaf2;
  --ink: #1c1712;
  --muted: #6d645a;
  --line: #e2d6c4;
  --accent: #c94b1a;
  --viral: #1e6b48;
  --shadow: 0 18px 40px rgba(48, 32, 12, .08);
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font: 15px/1.45 "Segoe UI", system-ui, sans-serif;
  color: var(--ink);
  background:
    radial-gradient(1200px 420px at 8% -10%, #fff8ea 0%, transparent 55%),
    var(--paper);
}
a { color: inherit; }
.wrap { width: min(1240px, calc(100% - 32px)); margin: 28px auto 64px; }
.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  margin-bottom: 22px;
}
.hero h1 {
  font-family: Georgia, "Iowan Old Style", serif;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -.03em;
  margin: 0 0 6px;
}
.hero p { margin: 0; color: var(--muted); max-width: 46rem; }
.stats { display: flex; gap: 10px; flex-wrap: wrap; }
.stat {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  min-width: 118px;
  padding: 12px 14px;
  box-shadow: var(--shadow);
}
.stat b { display: block; font-size: 22px; letter-spacing: -.03em; }
.stat span { color: var(--muted); font-size: 12px; }
.toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin: 18px 0;
}
input[type="search"], select {
  border: 1px solid var(--line);
  background: var(--card);
  border-radius: 999px;
  padding: 10px 14px;
  font: inherit;
  color: inherit;
}
input[type="search"] { min-width: min(100%, 280px); flex: 1; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip, .more, thead button {
  border: 1px solid var(--line);
  background: var(--card);
  color: inherit;
  border-radius: 999px;
  padding: 7px 12px;
  font: inherit;
  cursor: pointer;
}
.chip.is-on, thead button.is-on { background: var(--ink); color: #fff; border-color: var(--ink); }
.chip .n { color: var(--muted); padding-left: 6px; }
.chip.is-on .n { color: #f3d7c8; }
.board {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 22px;
  overflow: auto;
  box-shadow: var(--shadow);
}
table { width: 100%; border-collapse: collapse; min-width: 920px; }
th, td { padding: 12px 14px; text-align: left; vertical-align: top; }
thead th {
  position: sticky; top: 0; z-index: 2;
  background: #faf6ee;
  font-size: 12px;
  letter-spacing: .04em;
  text-transform: uppercase;
  color: var(--muted);
  border-bottom: 1px solid var(--line);
}
thead button { padding: 4px 8px; font-size: 12px; letter-spacing: .04em; text-transform: uppercase; }
tbody.item-block + tbody.item-block { border-top: 1px solid var(--line); }
.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.idx { color: var(--muted); width: 36px; }
.material { display: flex; gap: 12px; min-width: 280px; }
.cover, .ph {
  width: 96px; height: 68px; border-radius: 12px; object-fit: cover;
  background: #ece3d4; flex: none;
}
.ph { display: grid; place-items: center; color: #b09a82; font-size: 12px; }
.title {
  font-family: Georgia, serif;
  font-size: 17px;
  line-height: 1.3;
  text-decoration: none;
}
.title:hover { color: var(--accent); }
.meta { margin-top: 4px; color: var(--muted); font-size: 13px; }
.topic-pill {
  display: inline-block;
  background: #f3e6d4;
  border-radius: 999px;
  padding: 4px 9px;
  font-size: 13px;
}
.badge {
  display: inline-block;
  background: var(--viral);
  color: #fff;
  border-radius: 999px;
  padding: 3px 8px;
  font-size: 11px;
  letter-spacing: .04em;
  text-transform: uppercase;
}
.muted { color: var(--muted); }
.detail td {
  background: #fbf6ec;
  border-top: 1px dashed var(--line);
  padding: 0 14px 16px 122px;
}
.snippet { color: var(--muted); margin: 0 0 10px; }
.body {
  white-space: pre-wrap;
  max-height: 280px;
  overflow: auto;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 14px;
  padding: 12px 14px;
}
.gallery { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.gallery img { width: 120px; height: 80px; object-fit: cover; border-radius: 10px; }
.empty { padding: 28px; color: var(--muted); }
.hidden { display: none !important; }
@media (max-width: 720px) {
  .hero { flex-direction: column; align-items: flex-start; }
  .detail td { padding-left: 14px; }
}
"""

_JS = """
(function () {
  const blocks = Array.from(document.querySelectorAll("tbody.item-block"));
  const search = document.getElementById("q");
  const sort = document.getElementById("sort");
  const shown = document.getElementById("shown");
  const empty = document.getElementById("empty");
  const table = document.getElementById("board-table");
  let topic = "all";

  function apply() {
    const q = (search.value || "").trim().toLowerCase();
    let n = 0;
    blocks.forEach((block) => {
      const topicOk = topic === "all" || block.dataset.topic === topic;
      const textOk = !q || (block.dataset.search || "").indexOf(q) !== -1;
      const on = topicOk && textOk;
      block.classList.toggle("hidden", !on);
      if (on) n += 1;
    });
    shown.textContent = String(n);
    empty.classList.toggle("hidden", n !== 0);
    table.classList.toggle("hidden", n === 0);
  }

  document.querySelectorAll(".chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".chip").forEach((el) => el.classList.remove("is-on"));
      chip.classList.add("is-on");
      topic = chip.dataset.topic;
      apply();
    });
  });
  search.addEventListener("input", apply);
  sort.addEventListener("change", () => {
    const key = sort.value;
    const ranked = blocks.slice().sort((a, b) => {
      if (key === "title") {
        return (a.dataset.title || "").localeCompare(b.dataset.title || "", "ru");
      }
      return Number(b.dataset[key] || 0) - Number(a.dataset[key] || 0);
    });
    const parent = ranked[0] && ranked[0].parentElement;
    ranked.forEach((block) => parent.appendChild(block));
    apply();
  });
  document.querySelectorAll(".more").forEach((btn) => {
    btn.addEventListener("click", () => {
      const extra = btn.closest("tbody").querySelector(".detail");
      const open = extra.classList.toggle("hidden") === false;
      btn.textContent = open ? "Скрыть" : "Текст";
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  });
  const params = new URLSearchParams(location.search);
  if (params.get("q")) search.value = params.get("q");
  const startTopic = params.get("topic");
  if (startTopic) {
    document.querySelectorAll(".chip").forEach((chip) => {
      if (chip.dataset.topic === startTopic) chip.click();
    });
  }
  if (params.get("open") === "1") {
    const btn = document.querySelector(".item-block:not(.hidden) .more");
    if (btn) btn.click();
  }
  apply();
})();
"""


def format_int(value: object) -> str:
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return "0"
    return f"{number:,}".replace(",", " ")


def format_score(value: object) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def format_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    iso = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso)
    except ValueError:
        return text[:10]
    return f"{parsed.day} {_MONTHS_RU[parsed.month - 1]} {parsed.year}"


def date_sort_key(value: object) -> str:
    text = str(value or "").strip()
    return text[:10].replace("-", "") or "0"


def split_paths(value: object) -> list[str]:
    text = str(value or "")
    return [part.strip() for part in text.split("|") if part.strip()]


def media_src(stored: str, html_dir: Path) -> str:
    if not stored:
        return ""
    path = Path(stored)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.is_file():
        return ""
    try:
        return path.resolve().relative_to(html_dir.resolve(), walk_up=True).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def channel_href(url: object) -> str:
    text = str(url or "").strip()
    if not text or "{" in text or "}" in text:
        return ""
    if text.startswith("https://dzen.ru/") or text.startswith("http://dzen.ru/"):
        return text
    return ""


def _cover_src(row: Row, html_dir: Path, *, portable: bool = False) -> str:
    if not portable:
        local = media_src(str(row.get("cover_image_path") or ""), html_dir)
        if local:
            return local
    return str(row.get("cover_image_url") or "")


def _gallery(row: Row, html_dir: Path, *, portable: bool = False) -> list[str]:
    srcs: list[str] = []
    seen: set[str] = set()
    if not portable:
        for stored in split_paths(row.get("image_paths")):
            src = media_src(stored, html_dir)
            if src and src not in seen:
                seen.add(src)
                srcs.append(src)
        if srcs:
            return srcs[:8]
    for url in split_paths(row.get("image_urls")):
        if url not in seen:
            seen.add(url)
            srcs.append(url)
    return srcs[:8]


def merge_rows(groups: Sequence[Sequence[Row]]) -> list[dict[str, object]]:
    by_id: dict[str, dict[str, object]] = {}
    for group in groups:
        for row in group:
            item = dict(row)
            key = str(item.get("publication_id") or item.get("url") or "")
            if not key:
                continue
            prev = by_id.get(key)
            if prev is None or int(item.get("views") or 0) > int(prev.get("views") or 0):
                by_id[key] = item
    return sorted(
        by_id.values(),
        key=lambda item: (
            -int(item.get("is_viral") or 0),
            -float(item.get("viral_score") or 0),
            -int(item.get("views") or 0),
        ),
    )


def _row_html(row: Row, index: int, html_dir: Path, *, portable: bool = False) -> str:
    title = str(row.get("title") or "Без заголовка")
    topic = str(row.get("topic") or "без темы")
    url = str(row.get("url") or "")
    channel = str(row.get("channel_name") or "").strip()
    channel_url = channel_href(row.get("channel_url"))
    cover = _cover_src(row, html_dir, portable=portable)
    views = int(row.get("views") or 0)
    likes = int(row.get("likes") or 0)
    comments = int(row.get("comments") or 0)
    score = format_score(row.get("viral_score"))
    viral = bool(int(row.get("is_viral") or 0))
    published = format_date(row.get("published_at"))
    snippet = str(row.get("snippet") or "")
    body = str(row.get("full_text") or "")
    search = " ".join([title, topic, channel, snippet]).lower()
    cover_html = (
        f'<img class="cover" src="{html.escape(cover, quote=True)}" alt="">'
        if cover
        else '<div class="ph">нет фото</div>'
    )
    channel_html = html.escape(channel or "канал не указан")
    if channel_url:
        channel_html = (
            f'<a href="{html.escape(channel_url, quote=True)}" target="_blank" rel="noreferrer">'
            f"{channel_html}</a>"
        )
    title_html = html.escape(title)
    if url:
        title_html = (
            f'<a class="title" href="{html.escape(url, quote=True)}" target="_blank" rel="noreferrer">'
            f"{title_html}</a>"
        )
    else:
        title_html = f'<span class="title">{title_html}</span>'
    badge = '<span class="badge">вирус</span>' if viral else '<span class="muted">—</span>'
    gallery = "".join(
        f'<img src="{html.escape(src, quote=True)}" alt="">' for src in _gallery(row, html_dir, portable=portable)
    )
    extra_gallery = f'<div class="gallery">{gallery}</div>' if gallery else ""
    return f"""
<tbody class="item-block" data-topic="{html.escape(topic, quote=True)}" data-views="{views}"
  data-likes="{likes}" data-score="{html.escape(score, quote=True)}" data-date="{html.escape(date_sort_key(row.get('published_at')), quote=True)}"
  data-title="{html.escape(title, quote=True)}" data-search="{html.escape(search, quote=True)}">
  <tr class="item">
    <td class="idx num">{index}</td>
    <td>
      <div class="material">
        {cover_html}
        <div>
          {title_html}
          <div class="meta">{channel_html} · {html.escape(published)}</div>
        </div>
      </div>
    </td>
    <td><span class="topic-pill">{html.escape(topic)}</span></td>
    <td class="num">{html.escape(published)}</td>
    <td class="num">{format_int(views)}</td>
    <td class="num">{format_int(likes)}</td>
    <td class="num">{format_int(comments)}</td>
    <td class="num">{html.escape(score)}</td>
    <td>{badge}</td>
    <td><button type="button" class="more" aria-expanded="false">Текст</button></td>
  </tr>
  <tr class="detail hidden">
    <td colspan="10">
      <p class="snippet">{html.escape(snippet) or "Сниппета нет."}</p>
      <div class="body">{html.escape(body) or "Полного текста нет."}</div>
      {extra_gallery}
    </td>
  </tr>
</tbody>
"""


def export_html(
    rows: Sequence[Row],
    html_path: str | Path,
    *,
    title: str = "Вирусный Дзен",
    subtitle: str = "Заголовки, охваты, даты и текст — чтобы было видно, что уже крутится.",
    portable: bool = False,
) -> Path:
    path = Path(html_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    html_dir = path.parent
    items = [dict(row) for row in rows]
    topics = Counter(str(item.get("topic") or "без темы") for item in items)
    viral_n = sum(1 for item in items if int(item.get("is_viral") or 0))
    views_n = sum(int(item.get("views") or 0) for item in items)
    chips = ['<button type="button" class="chip is-on" data-topic="all">Все<span class="n">' + str(len(items)) + "</span></button>"]
    for topic, count in topics.most_common():
        chips.append(
            f'<button type="button" class="chip" data-topic="{html.escape(topic, quote=True)}">'
            f"{html.escape(topic)}<span class=\"n\">{count}</span></button>"
        )
    body_rows = "".join(
        _row_html(item, index, html_dir, portable=portable)
        for index, item in enumerate(items, start=1)
    )
    page = f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
  <div class="wrap">
    <header class="hero">
      <div>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(subtitle)} Показано <b id="shown">{len(items)}</b> из {len(items)}.</p>
      </div>
      <div class="stats">
        <div class="stat"><b>{len(items)}</b><span>материалов</span></div>
        <div class="stat"><b>{viral_n}</b><span>с флагом вирус</span></div>
        <div class="stat"><b>{format_int(views_n)}</b><span>просмотров суммарно</span></div>
        <div class="stat"><b>{len(topics)}</b><span>тем</span></div>
      </div>
    </header>
    <div class="toolbar">
      <input id="q" type="search" placeholder="Поиск по заголовку, теме, каналу">
      <select id="sort" aria-label="Сортировка">
        <option value="score">Сначала сильный скор</option>
        <option value="views">Сначала просмотры</option>
        <option value="likes">Сначала лайки</option>
        <option value="date">Сначала новые</option>
        <option value="title">По алфавиту</option>
      </select>
    </div>
    <div class="chips">{"".join(chips)}</div>
    <div class="board" id="board">
      <table id="board-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Материал</th>
            <th>Тема</th>
            <th>Дата</th>
            <th class="num">Просмотры</th>
            <th class="num">Лайки</th>
            <th class="num">Коммент.</th>
            <th class="num">Скор</th>
            <th>Вирус</th>
            <th></th>
          </tr>
        </thead>
        {body_rows}
      </table>
      <div id="empty" class="empty hidden">Ничего не нашлось по фильтру.</div>
    </div>
  </div>
  <script>{_JS}</script>
</body>
</html>
"""
    path.write_text(page, encoding="utf-8")
    return path
