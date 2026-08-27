# ViralDzen

Сбор вирусного контента с [Дзена](https://dzen.ru) **без браузера**: HTTP + публичные JSON-эндпоинты. На выходе таблица с датами, заголовками, текстом, картинками и метриками — человеку удобнее всего открыть **`data/viral.html`**.

Тема всегда ваша: слова (официальный хаб Дзена) или ссылка на канал, статью `dzen.ru/a/...` или хаб `dzen.ru/topic/...`. Скрипт сам подскажет, о чём канал или статья.

## Установка

Нужен Python 3.11+. Сторонних пакетов нет.

### 1. Клонировать и открыть в Cursor (рекомендуется)

Скилл, субагенты и CLI поднимаются сами: достаточно открыть репозиторий.

```bash
git clone https://github.com/Horosheff/ViralDzen.git
cd ViralDzen
python3 -m unittest discover -s tests -v
```

Откройте папку в Cursor, Claude Code, Codex или другом агенте с поддержкой [Agent Skills](https://agentskills.io/specification). Скилл лежит сразу в трёх местах, которые клиенты обычно сканируют:

- `.cursor/skills/viraldzen-collect/`
- `.agents/skills/viraldzen-collect/`
- `skills/viraldzen-collect/`

### 2. Поставить скилл в другой проект / глобально

```bash
npx skills add Horosheff/ViralDzen
```

Или GitHub CLI:

```bash
gh skill install Horosheff/ViralDzen --agent cursor --scope user
```

CLI после этого:

```bash
pip install "git+https://github.com/Horosheff/ViralDzen.git"
python3 -m viraldzen -h
```

Из клона одной командой: `./install-skill.sh` — копирует скилл в `~/.cursor/skills`, `~/.agents/skills`, `~/.claude/skills` и ставит пакет в editable-режиме.

### 3. Только CLI, без агента

```bash
pip install "git+https://github.com/Horosheff/ViralDzen.git"
python3 -m viraldzen topics --query здоровье
```

## Как устроен вирусный контент в Дзене

У Дзена нет официального API «вирусных статей». В продукте это выглядит так:

1. Открываете статью по теме.
2. Прокручиваете вниз — под материалом подгружается **подборка офферов**: бесконечная лента похожих карточек (endless article / recirc).
3. Среди них оказываются материалы, которые рекомендательная система уже раскрутила: много просмотров, дочитываний, реакций.

Браузер для этого не нужен. Те же данные отдают внутренние, но публично доступные ручки:

| Что нужно | Откуда берём |
| --- | --- |
| Официальные темы (куда смотреть) | `GET /api/web/v1/zen-search?forced_request_type=topic_channel_search&type_filter=topic_channel&query=...` |
| Поиск по теме | `GET /api/web/v1/zen-search?forced_request_type=media_search&query=...&type_filter=brief,article` |
| Пагинация поиска | поле `feedData.more.link` / `more.link` |
| Рекомендательная лента | `GET /api/v3/launcher/export` и `.../more` |
| Канал автора | `GET /api/v3/launcher/export?channel_name=` или `channel_id=` |
| Полный текст, обложка, картинки из статьи | HTML `https://dzen.ru/a/{id}` → JSON `ssrData.publishersResponse` (Draft.js) |
| Подборка «офферов» вокруг материала | уточняющий поиск `тема + слова из заголовка` и лента канала автора |

Виральность считаем сами: просмотры важнее шумного ER на маленькой выборке, плюс дочитывания, лайки, комментарии и свежесть. Флаг `is_viral` — выброс по просмотрам, верхний квартиль скора, высокий ER или сильное дочитывание. Кликбейт-тесты («если сможете ответить на 8/10») понижаются. Общая рекомендательная лента в таблицу не попадает, пока заголовок/текст не совпадают с темой.

## Куда смотреть

Дзен держит **официальные хабы** (`dzen.ru/topic/...`). Каталога без запроса нет: по вашим словам поиск возвращает хабы с числом подписчиков.

```bash
python3 -m viraldzen topics --query здоровье
python3 -m viraldzen collect --topic здоровье --pick 1 --out-dir data
python3 -m viraldzen collect --slug zdorove --out-dir data
```

Либо пришлите **ссылку**: канал, статья `dzen.ru/a/...` или хаб `dzen.ru/topic/...`:

```bash
python3 -m viraldzen channel --url https://dzen.ru/<канал>
python3 -m viraldzen collect --channel https://dzen.ru/<канал> --channel-limit 3 --out-dir data
python3 -m viraldzen collect --channel https://dzen.ru/<канал> --channel-only --out-dir data
python3 -m viraldzen collect --url https://dzen.ru/a/<id> --out-dir data
python3 -m viraldzen collect --url https://dzen.ru/topic/zdorove --out-dir data
```

В терминале достаточно `python3 -m viraldzen collect --out-dir data`: скрипт спросит тему и покажет хабы. Без TTY нужны `--topic` / `--slug` / `--channel`. Узкая фраза без хаба: `--raw-topic`.

## Быстрый старт

```bash
python3 -m viraldzen topics --query здоровье
python3 -m viraldzen collect --topic здоровье --pick 1 --pages 2 --top 20 --out-dir data
python3 -m viraldzen table --db data/viral.sqlite --limit 20
python3 -m viraldzen export --db data/viral.sqlite --csv data/viral.csv
```

Несколько тем — скопируйте `topics.example.json` в `topics.json` и подставьте свои запросы:

```bash
cp topics.example.json topics.json
python3 -m viraldzen collect --config topics.json --out-dir data
```

Флаги: `--no-content`, `--no-images`, `--no-recirc`, `--no-feed`, `--min-views 1000`, `--delay 0.7`, `--topic-limit 20`, `--topic-sort subscribers`.

## Таблица

SQLite `data/viral.sqlite` и CSV `data/viral.csv` (UTF-8 BOM). Поля:

`publication_id`, `url`, `title`, `topic`, `source_kind`, `published_at`, `collected_at`, `channel_name`, `channel_url`, `views`, `views_till_end`, `likes`, `comments`, `read_through`, `engagement_rate`, `viral_score`, `is_viral`, `cover_image_url`, `cover_image_path`, `image_urls`, `image_paths`, `snippet`, `full_text`, `recirc_parent_url`, `tags`.

Картинки — `data/images/<id>/`.

```bash
python3 -m viraldzen html --db data/viral.sqlite --out data/viral.html
python3 -m viraldzen html --db data/a/viral.sqlite --db data/b/viral.sqlite --out data/board.html --title "Вирусный Дзен"
```

`--portable` — один файл с картинками по URL Дзена (можно сразу на `collect`). `collect` сам кладёт `viral.html` рядом с CSV: фильтры, сортировка, кнопка «Текст».

`source_kind`: `search`, `feed`, `recirc`, `channel`.

## Алгоритм сбора

1. Прогреть cookies обычным JSON-запросом к Дзену.
2. Получить официальные темы по словам **или** разобрать канал и взять похожие хабы.
3. По названию темы выбрать статьи/посты через `zen-search`.
4. Подмешать карточки из рекомендательной ленты, если они попадают в тему.
5. Посчитать `viral_score`, взять top-N.
6. Для лучших семян сходить в подборку офферов (уточняющий поиск и канал автора).
7. Вытащить полный текст и картинки из SSR, пересчитать скор.
8. Скачать изображения, записать SQLite, CSV и HTML.

Браузер не используется.

## Для агентов

Плейбук: `skills/viraldzen-collect/SKILL.md` (те же файлы в `.cursor/skills/` и `.agents/skills/`). Конституция: `AGENTS.md`. Субагенты Cursor: `dzen-topics`, `dzen-channel`, `dzen-collect`, `dzen-table`.

Агент здоровается, спрашивает тему или ссылку и в конце отдаёт HTML-таблицу. Чужие пресеты не подставляет.

## Тесты

```bash
python3 -m unittest discover -s tests -v
```

Живой смоук (нужен доступ к dzen.ru):

```bash
python3 -m viraldzen topics --query здоровье --limit 5
python3 -m viraldzen collect --topic здоровье --pick 1 --pages 1 --top 5 --out-dir data/smoke --delay 0.5
```

## Важно

- Это неофициальные эндпоинты Дзена, они могут меняться.
- Соблюдайте паузы (`--delay`) и не долбите API.
- Собранный текст чужих статей — для рерайта, не для копипаста. Сырые выгрузки в git не коммитятся (`data/` в `.gitignore`).
- Логин в Яндекс не нужен: читаем публичные материалы.

## Лицензия

[MIT](LICENSE)

---

Создано для того, чтобы автоматизировать рутину и вернуть время на творчество!

💬 Связь с разработчиком и обновления: [@maya_pro](https://t.me/maya_pro)
