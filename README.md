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
- canonical NPC TALK со структурированным изменением familiarity.

## Локальный запуск

Требуется Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

## Демо ядра

После editable install:

```bash
python scripts/demo_shared_world.py
```

Сценарий доказывает четыре свойства MVP-A: два игрока видят один предмет; действие первого меняет вид второго; изменение переживает переоткрытие БД; NPC меняет состояние после продвижения `FakeClock`.

## Архитектурный принцип

```text
adapter -> CanonicalAction -> GameService -> deterministic rules -> SQLite transaction
                                                              -> ActionEvent
                                                              -> ProgressionEngine
```

Только authoritative simulation layer меняет канонический мир. Discord, parser, renderer и LLM работают поверх этого API.

## Текущий scope

Сейчас намеренно отсутствуют combat, crafting, большой мир, dynamic lighting, автономные LLM-NPC, vector DB/RAG, PostgreSQL/Redis и Discord Activity. Следующий продуктовый слой — детерминированная мировая сводка / «что изменилось, пока меня не было», собранная только из канонического состояния и событий.

## Discord founder build

Discord слой использует slash commands и не читает обычные сообщения сервера.

1. Создайте Application/Bot в Discord Developer Portal и добавьте его на тестовый сервер с правом использования application commands.
2. Установите optional extra:

```bash
pip install -e '.[dev,discord]'
```

3. Задайте переменные окружения:

```bash
export DISCORD_BOT_TOKEN='...'
export DISCORD_GUILD_ID='123456789012345678'  # рекомендуется для быстрого dev-sync
export SAM_SEBE_DB='./game.db'                 # необязательно
```

4. Запустите:

```bash
python -m samseberpg.discord_bot
```

Команды MVP:

- `/look` — осмотреть текущее место;
- `/me` — показать локацию, монеты, инвентарь и progression;
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

## Persistent consequences slice

Ядро поддерживает действия, которые создают наблюдаемые последствия:

- `THROW` — принадлежащий игроку throwable-предмет может детерминированно повредить объект с `condition`; предмет после броска остаётся в локации;
- `GIVE` — предмет передаётся присутствующему actor; еда, подаренная NPC, меняет его отношение к игроку.

Пример:

```text
взять stone_flat_1
идти village_square
бросить stone_flat_1 в tavern_sign
```

После этого другой игрок на площади увидит у вывески изменённое состояние. Если Орен находился на площади и видел бросок, его `trust` к игроку уменьшается, а `conflict` растёт. Эти изменения хранятся в SQLite и переживают restart.

Позитивный пример:

```text
взять bread_1
дать bread_1 npc_oren
```

Проверочный сценарий:

```bash
python scripts/demo_consequences.py
```

## Minimal Economy + USE slice

У игрока 10 стартовых монет, у Орена — канонический баланс, а `bottle_1` выставлена на площади за 3 монеты. Обычный `TAKE` не позволяет обойти продажу.

```text
идти village_square
купить bottle_1 у npc_oren
использовать bottle_1 на village_well
```

После покупки у игрока остаётся 7 монет, Орен получает 3, а бутылка становится собственностью игрока. Использование бутылки на колодце меняет её каноническое состояние на `filled_with=water`. Деньги, ownership и содержимое переживают restart; повтор одного Discord interaction ID не списывает оплату повторно.

Проверочный сценарий:

```bash
python scripts/demo_economy_use.py
```

## SQLite migrations

`GameDatabase.initialize()` использует `PRAGMA user_version` и автоматически обновляет старые founder DB до текущего schema/data contract. Текущая версия — `3`; v3 добавляет persistent progression tables. Миграции не удаляют мир и не сбрасывают player coins, ownership, relations, events или существующее состояние объектов. DB из более новой неизвестной версии отклоняется с typed error вместо рискованного downgrade.

Проверить апгрейд representative legacy DB:

```bash
python scripts/demo_migration.py
```

## Natural-language intent provider

`/act` имеет два уровня интерпретации:

1. точная grammar (`взять stone_flat_1`, `идти village_square`, `сказать npc_mira привет` и т. п.) всегда проверяется первой и не требует AI;
2. если точная grammar не подошла и явно задан `OLLAMA_MODEL`, обычная фраза передаётся optional semantic provider.

LLM получает только компактный canonical context: текущую локацию, доступные выходы, видимых actors/entities, inventory и баланс. Его structured proposal ещё раз локально проверяется по allow-list текущего контекста и только после этого превращается в `CanonicalAction`. Любой выдуманный ID, неподдерживаемая механика, попытка TALK со скрытым NPC/игроком или ошибка провайдера не создаёт gameplay event и не меняет каноническое состояние.

Для локального Ollama runtime:

```bash
export OLLAMA_MODEL='<имя уже установленной локальной модели>'
export OLLAMA_URL='http://127.0.0.1:11434'       # необязательно
export OLLAMA_TIMEOUT_SECONDS='5'                # необязательно, максимум 30
python -m samseberpg.discord_bot
```

Если `OLLAMA_MODEL` не задан, Discord build продолжает работать только на deterministic grammar.

Проверить semantic integration без сети:

```bash
python scripts/demo_natural_language.py
```

Этот demo использует deterministic fake resolver только для проверки контракта `natural phrase -> proposal -> context guard -> GameService`. В текущей среде разработки бинарник/model Ollama отсутствует, поэтому реальная inference здесь не заявляется как проверенная.

## Emergent Progression v0

Первая рабочая ветка проверяет ключевую фантазию `Behavior -> Achievement -> Skill`.

Игрок не выбирает класс. После 3 успешных `THROW` с минимум 2 разными projectile ID система открывает:

- достижение `THROWING_HABIT_1` — **«Рука помнит дугу»**;
- навык `STEADY_HAND` — **«Твёрдая рука»**.

Триггерный третий бросок ещё выполняется по старым правилам. Начиная со следующего броска `STEADY_HAND` добавляет +5 impact damage. Unlock хранится в SQLite, переживает restart, отображается в `/me` и возвращается idempotently при повторе того же Discord interaction.

Проверочный сценарий:

```bash
python scripts/demo_progression.py
```

## NPC TALK v0

`TALK` — каноническое действие, а не свободная LLM-мутация мира. Поговорить можно только с NPC, который физически присутствует в текущей локации.

Успешный разговор:

- записывается в `action_events`;
- сохраняет исходную фразу игрока;
- сохраняет текущую activity NPC;
- увеличивает `familiarity` NPC к игроку на 1 с clamp до 100;
- не удваивается при replay того же interaction ID.

Exact формы:

```text
говорить npc_mira
сказать npc_mira привет
talk npc_mira
say npc_mira hello there
```

Semantic TALK тоже разрешён, но canonicalizer принимает только видимого NPC и отбрасывает игрока или скрытый/выдуманный ID до `GameService`.

Проверочный сценарий:

```bash
python scripts/demo_talk.py
```
