# Sam-Sebe-RPG — Emergent RPG / Living World

Экспериментальная multiplayer-first текстовая RPG с одним общим persistent-миром. Каноническое состояние хранится в SQLite; Discord и optional LLM-слой являются адаптерами и не могут менять состояние напрямую.

## Что уже реализовано

- одна деревня: 3 локации, 3 NPC, 12 стартовых объектов;
- несколько игроков в одном каноническом мире;
- Discord user ID -> стабильный player actor;
- LOOK / MOVE / TAKE / DROP / THROW / GIVE / BUY / USE / TALK;
- атомарные SQLite-транзакции и append-only action events;
- idempotency по external interaction ID;
- persistence после перезапуска;
- `SystemClock` / `FakeClock`;
- lazy catch-up расписаний NPC без постоянного tick-loop;
- защита конкурентного TAKE через `BEGIN IMMEDIATE`;
- persistent object damage и witness-dependent consequences;
- минимальная экономика BUY + USE;
- safe schema migrations до v3;
- optional natural-language intent через Ollama structured output;
- первая ветка emergent progression `Behavior -> Achievement -> Skill`;
- canonical NPC TALK со структурированным изменением familiarity;
- детерминированная `/news` сводка «что изменилось после моей последней активности».

## Локальный запуск

Требуется Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

## Архитектурный принцип

```text
adapter -> CanonicalAction -> GameService -> deterministic rules -> SQLite transaction
                                                              -> ActionEvent
                                                              -> ProgressionEngine

canonical state + action_events -> WorldDigestService -> /news
```

Только authoritative simulation layer меняет канонический мир. Discord, parser, renderer, digest и LLM работают поверх канонических API/данных.

## Discord founder build

Discord слой использует slash commands и не читает обычные сообщения сервера.

```bash
pip install -e '.[dev,discord]'
export DISCORD_BOT_TOKEN='...'
export DISCORD_GUILD_ID='123456789012345678'  # рекомендуется для быстрого dev-sync
export SAM_SEBE_DB='./game.db'                 # необязательно
python -m samseberpg.discord_bot
```

Команды MVP:

- `/look` — осмотреть текущее место;
- `/me` — показать локацию, монеты, инвентарь и progression;
- `/news` — увидеть значимые изменения мира после своей последней gameplay-активности;
- `/act text:осмотреться`;
- `/act text:идти village_square`;
- `/act text:взять stone_flat_1`;
- `/act text:положить stone_flat_1`;
- `/act text:бросить stone_flat_1 в tavern_sign`;
- `/act text:дать bread_1 npc_oren`;
- `/act text:купить bottle_1 у npc_oren`;
- `/act text:использовать bottle_1 на village_well`;
- `/act text:говорить npc_mira`;
- `/act text:сказать npc_mira привет`.

Если `DISCORD_GUILD_ID` задан, команды синхронизируются только с этим тестовым сервером. Без него выполняется global sync.

## Проверочные сценарии

```bash
python scripts/demo_shared_world.py
python scripts/demo_consequences.py
python scripts/demo_economy_use.py
python scripts/demo_migration.py
python scripts/demo_natural_language.py
python scripts/demo_progression.py
python scripts/demo_talk.py
python scripts/demo_world_digest.py
```

## Persistent consequences

`THROW` может детерминированно повредить объект с `condition`, а NPC-свидетели меняют структурированные отношения. `GIVE` передаёт ownership; еда, подаренная NPC, меняет `trust/affinity`. Все изменения переживают restart.

## Minimal Economy + USE

У игрока 10 стартовых монет. `bottle_1` выставлена Ореном за 3 монеты; обычный `TAKE` не обходит продажу. `BUY` атомарно переводит деньги и ownership, а `USE bottle_1 -> village_well` записывает `filled_with=water`.

## SQLite migrations

`GameDatabase.initialize()` использует `PRAGMA user_version`. Текущая версия — `3`; v3 добавляет persistent progression tables. Миграции сохраняют player coins, ownership, relations, events и существующее состояние объектов. Более новая неизвестная версия БД отклоняется вместо рискованного downgrade.

## Natural-language intent provider

`/act` сначала использует deterministic grammar. Только на parser-miss и при заданном `OLLAMA_MODEL` подключается semantic resolver.

LLM получает компактный canonical context и возвращает structured proposal. Proposal повторно проверяется локально: выдуманный ID, недоступная локация, чужой item, TALK со скрытым NPC/игроком или неподдерживаемая механика отбрасываются до `GameService`.

```bash
export OLLAMA_MODEL='<имя уже установленной локальной модели>'
export OLLAMA_URL='http://127.0.0.1:11434'       # необязательно
export OLLAMA_TIMEOUT_SECONDS='5'                # необязательно, максимум 30
```

В текущей среде разработки реальный Ollama runtime/model отсутствует; HTTP/JSON-schema contract проверяется без сети.

## Emergent Progression v0

После 3 успешных `THROW` с минимум 2 разными projectile ID система детерминированно открывает:

- `THROWING_HABIT_1` — **«Рука помнит дугу»**;
- `STEADY_HAND` — **«Твёрдая рука»**.

Триггерный бросок выполняется без бонуса. Следующие броски получают +5 impact damage. Unlock хранится в SQLite, переживает restart, показывается в `/me` и возвращается idempotently при replay interaction.

## NPC TALK v0

`TALK` — каноническое действие. Поговорить можно только с NPC в текущей локации. Успех записывает исходную фразу, текущую activity NPC и увеличивает bounded `familiarity` на 1. Exact и semantic TALK проходят один и тот же authoritative путь.

## World Digest v0

`/news` — первая механика возвращения в живой мир.

Сводка вычисляет `since_event_id` как последнее gameplay-событие самого игрока и показывает после него до 8 успешных значимых действий других игроков (`THROW`, `GIVE`, `BUY`). Она также всегда показывает текущее persistent-повреждение объектов и глобальное положение/activity NPC после lazy catch-up.

`/news` не создаёт action events и не использует LLM. Повторный запрос при неизменном мире возвращает тот же результат. Это фундамент для будущей утренней газеты; scheduled 09:00 delivery, погода, слухи и narrative prose пока намеренно отложены.

## Текущий scope

Намеренно отсутствуют combat, crafting, большой мир, dynamic lighting, автономные LLM-NPC, vector DB/RAG, PostgreSQL/Redis, Discord Activity и фоновая генерация контента. Следующий полезный слой должен усиливать один из уже проверяемых core-сигналов, а не расширять мир по площади.
