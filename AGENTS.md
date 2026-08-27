# AGENTS.md

ViralDzen — библиотека: вирусные материалы Дзена по теме, которую назвал человек. Без браузера, без логина в Яндекс.

Отвечай по-русски. Плейбук смены — `skills/viraldzen-collect/SKILL.md` (копии: `.cursor/skills/viraldzen-collect/`, `.agents/skills/viraldzen-collect/`). README — людям, сюда не копируй.

В репозитории нет чужих сайтов, каналов и списков тем «под автора». Тема всегда от текущего пользователя.

## Старт

Пока человек не назвал тему и не прислал ссылку Дзена — не запускай `collect`. Поприветствуй: слова, канал, статья или хаб `dzen.ru/topic/…`. В конце смены человек должен получить HTML-таблицу.

## Куда писать

- Статус после работы — `handoff.md` (в git не коммитить)
- Сырые выгрузки — только в `data/`

## Запреты

- Не подставлять чужие темы, сайты и каналы из прошлых чатов
- Не копипастить статью Дзена как готовый материал человека
- Не коммитить `data/`, ключи, cookies, заполненный `handoff.md`
- Не открывать браузер, если хватает `python3 -m viraldzen`
- Не ждать `input()`: у агента нет TTY. Флаги `--topic` / `--slug` / `--pick` / `--channel` / `--url` / `--channel-only`

## Как проверить, что смена закрыта

1. Человека поприветствовали и спросили тему **или** канал, если он сам это не принёс
2. В `handoff.md` есть статус, команда, выбранная тема (название + slug + подписчики, если хаб нашёлся) или канал/статья, **путь к HTML**, CSV/SQLite, число строк
3. Если меняли код — `python3 -m unittest discover -s tests -v` зелёный
4. В git-диффе нет `data/` и cookies

## Команды

```bash
python3 -m viraldzen topics --query "<тема>"
python3 -m viraldzen channel --url "https://dzen.ru/<канал>"
python3 -m viraldzen collect --topic "<тема>" --pick 1 --pages 2 --top 20 --out-dir data
python3 -m viraldzen collect --channel "https://dzen.ru/<канал>" --channel-limit 3 --out-dir data
python3 -m viraldzen collect --channel "https://dzen.ru/<канал>" --channel-only --out-dir data
python3 -m viraldzen collect --url "https://dzen.ru/a/<id>" --out-dir data
python3 -m viraldzen html --db data/viral.sqlite --out data/viral.html
python3 -m unittest discover -s tests -v
```
