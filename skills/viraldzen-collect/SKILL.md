---
name: viraldzen-collect
description: Collect viral Dzen (Дзен) content without a browser via python3 -m viraldzen. Use when collecting viral articles, greeting the user to pick an official topic, studying a Dzen channel or article URL, scoring a channel's own feed (--channel-only), exporting HTML/CSV/SQLite, or the user says сбор вирусного, дзен, официальные темы, канал, таблица, viraldzen. Always answer in Russian. Greet first. End with an HTML table the human can open. Do not invent a topic. Do not open a browser if the CLI is enough.
license: MIT
compatibility: Requires Python 3.11+ and network access to dzen.ru. No third-party Python packages.
---

# Сбор вирусного Дзена

Конституция — корневой `AGENTS.md`, если открыт клон репозитория. README в чат не копируй. Ручки API — [references/dzen-api.md](references/dzen-api.md), если чинишь сборщик. Установка CLI — [references/install.md](references/install.md). Статус — [references/handoff.md](references/handoff.md).

Тема только от этого пользователя. Чужие сайты и каналы из прошлых чатов не подставляй.

## Когда включать

Вирусное с Дзена, официальная тема, канал, статья, HTML-таблица.

Не включать, если просят только поменять парсер/скор и не собирать.

## Окружение

Перед первым сбором проверь CLI. Если `python3 -m viraldzen -h` не работает:

```bash
pip install "git+https://github.com/Horosheff/ViralDzen.git"
```

Из клона репозитория pip не нужен: команды запускай из корня клона. Python 3.11+, сеть до `dzen.ru`.

## Ритм смены

Не запускай `collect`, пока нет темы или ссылки Дзена. Не выдумывай тему «для примера».

### 1. Приветствие

По-русски. Логин в Яндекс не нужен. Браузер не нужен.

Если в сообщении уже есть тема, slug или ссылка `dzen.ru/...` — коротко поздоровайся и иди на шаг 2–4.

Если ничего нет — одно сообщение, без `input()` в терминале:

> Привет. Соберу вирусные материалы Дзена по вашей теме — без браузера и без логина.
>
> Как выбираем, куда смотреть?
> 1. Напишите тему словами. Покажу официальные хабы с числом подписчиков, выберете номер.
> 2. Пришлите ссылку на канал (`dzen.ru/<имя>` или `dzen.ru/id/...`). Разберу, о чём канал.
> 3. Можно ссылку на статью (`dzen.ru/a/...`) или на хаб (`dzen.ru/topic/...`).

Дальше жди ответ.

### 2. Тема словами

```bash
python3 -m viraldzen topics --query "<слова человека>" --limit 20
```

Вставь таблицу как есть. Спроси номер, `1,3`, slug или «все». Хаба нет — `--raw-topic`, не подменяй соседним миллионным хабом.

### 3. Ссылка Дзена

```bash
python3 -m viraldzen channel --url "<ссылка>"
```

Команда сама отличит канал, статью и `topic/<slug>`. Покажи хабы, спроси номер, если человек ещё не сказал «собирай».

Видео и shorts не берём: нужен текст статьи.

### 4. Ресерч

Без TTY, только флаги.

```bash
python3 -m viraldzen collect --topic "<запрос>" --pick 1 --pages 2 --top 20 --out-dir data --delay 0.7
python3 -m viraldzen collect --slug <slug> --out-dir data
python3 -m viraldzen collect --channel "<канал>" --pick 1 --out-dir data --delay 0.7
python3 -m viraldzen collect --url "<любая ссылка dzen.ru>" --pick 1 --out-dir data --delay 0.7
python3 -m viraldzen collect --channel "<канал>" --channel-only --out-dir data --delay 0.7
```

После `channel` **спроси номер хаба**. Не запускай collect по каналу/статье без `--pick`, если человек не сказал «собери с этого канала» (`--channel-only`) или «бери первый». Без `--pick` CLI молча возьмёт первые N хабов — это эвристика, рядом может оказаться чужой миллионный хаб.

Узкая фраза без хаба: `--raw-topic`. Только крупный охват: `--min-views 10000`. Несколько тяжёлых тем — субагенты `dzen-collect` в **разные** `--out-dir`.

`--delay` обязателен. Сеть один раз упала — повтор. Второй провал — блокер в `handoff.md`.

### 5. Главное для человека: HTML

`collect` сам пишет `data/viral.html`. Это то, что человек открывает: фильтры, сортировка, кнопка «Текст», обложки, просмотры.

В ответе **сначала** путь к HTML, потом 3–5 заголовков с просмотрами, потом CSV/SQLite. Сырой `full_text` в чат не вываливай.

Один файл «скачать и открыть без папки картинок» — сразу на сборе:

```bash
python3 -m viraldzen collect --slug <slug> --out-dir data --delay 0.7 --portable
```

или отдельно:

```bash
python3 -m viraldzen html --db data/viral.sqlite --out data/viral.html --portable
```

Проверку таблицы можно отдать `dzen-table`.

### 6. Закрытие

`handoff.md`. `data/` и cookies в git не клади.

## Насколько это «точно»

У Дзена нет ручки «верни вирусное». Мы берём публичный поиск/ленту/канал/SSR и **сами** считаем скор.

- Просмотры, дочитывания, лайки, дата — из JSON/SSR Дзена, как у обычной карточки. Это не кабинет автора.
- `viral_score` / `is_viral` — наша эвристика (охват важнее шумного ER). Флаг `is_viral` ещё и **относительный к текущей выборке**: в топ-5 почти все будут с флажком. Человеку говори просмотры и заголовок, не «Дзен пометил как вирус».
- Попадание в тему — слово или склонение (`здоровье` ≈ `здоровья`), не «здорово». Карточки из поиска Дзен может подмешать смежные; recirc тянет соседей офферов.
- Канал/статья → хабы — эвристика по тегам и заголовкам. Человек должен увидеть таблицу хабов и выбрать. Не собирай молча «Чемпионат Японии», если канал про философию.
- «Вирусное с этого канала» и «вирусное по теме канала на всём Дзене» — разные запросы. Первое: `--channel-only`. Второе: хабы + `--pick`.
- Видео, shorts, комментарии, Wordstat и каталог всех хабов без запроса не собираем.

## Субагенты

Родитель здоровается и отдаёт HTML человеку. Субагенты не выдумывают тему.

| Кого звать | Когда |
| --- | --- |
| `dzen-topics` | Слова есть, нужен список хабов |
| `dzen-channel` | Любая ссылка dzen.ru |
| `dzen-collect` | Тема или ссылка уже выбраны |
| `dzen-table` | После сбора: HTML для человека |

## Готово

Поздоровались. Тема или ссылка — его. На диске HTML (или честный блокер). В чат — путь к таблице и топ заголовков, не портянка текста.
