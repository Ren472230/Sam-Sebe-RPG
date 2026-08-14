# Sam-Sebe-RPG — Emergent RPG / Living World

Экспериментальная multiplayer-first текстовая RPG с одним общим persistent-миром. Каноническое состояние хранится в SQLite; Discord и будущий LLM-слой являются адаптерами и не могут менять состояние напрямую.

## Что уже реализовано в Shared World Kernel

- одна деревня: 3 локации, 3 NPC, 12 стартовых объектов;
- несколько игроков в одном каноническом мире;
- Discord user ID -> стабильный player actor;
- LOOK / MOVE / TAKE / DROP / THROW / GIVE / BUY / USE;
- атомарные SQLite-транзакции и append-only action events;
- idempotency по external interaction ID;
- persistence после перезапуска;
- `SystemClock` / `FakeClock`;
- lazy catch-up расписаний NPC без постоянного tick-loop;
- защита конкурентного TAKE через `BEGIN IMMEDIATE`;
- deterministic demo двух игроков.

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
```

Только `GameService`/simulation layer меняет канонический мир. Discord, parser, renderer и LLM работают поверх этого API.

## Текущий scope

Сейчас намеренно отсутствуют combat, crafting, большой мир, dynamic lighting, автономные LLM-NPC, vector DB/RAG, PostgreSQL/Redis и Discord Activity. Discord adapter, persistent consequences и минимальный BUY/USE loop уже есть. Следующий продуктовый слой — безопасная эволюция схемы БД и natural-language intent provider.

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
- `/me` — показать локацию и инвентарь;
- `/act text:осмотреться`;
- `/act text:идти village_square`;
- `/act text:взять stone_flat_1`;
- `/act text:положить stone_flat_1`;
- `/act text:бросить stone_flat_1 в tavern_sign`;
- `/act text:дать bread_1 npc_oren`;
- `/act text:купить bottle_1 у npc_oren`;
- `/act text:использовать bottle_1 на village_well`.

Если `DISCORD_GUILD_ID` задан, команды синхронизируются только с этим тестовым сервером. Без него выполняется global sync.

## Persistent consequences slice

Ядро уже поддерживает два действия, которые создают наблюдаемые последствия:

- `THROW` — принадлежащий игроку throwable-предмет может детерминированно повредить объект с `condition`; предмет после броска остаётся в локации;
- `GIVE` — предмет передаётся присутствующему actor; еда, подаренная NPC, меняет его отношение к игроку.

Пример для текущей деревни:

```text
взять stone_flat_1
идти village_square
бросить stone_flat_1 в tavern_sign
```

После этого другой игрок на площади увидит у вывески `состояние: 80%`. Если Орен находился на площади и видел бросок, его `trust` к игроку уменьшается, а `conflict` растёт. Эти изменения хранятся в SQLite и переживают restart.

Позитивный пример:

```text
взять bread_1
дать bread_1 npc_oren
```

Запустить автономный сценарий проверки:

```bash
python scripts/demo_consequences.py
```

## Minimal Economy + USE slice

В деревне есть один намеренно маленький экономический loop. У игрока 10 стартовых монет, у Орена — канонический баланс, а `bottle_1` выставлена на площади за 3 монеты. Обычный `TAKE` не позволяет обойти продажу.

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

`GameDatabase.initialize()` использует `PRAGMA user_version` и автоматически обновляет старые founder DB до текущего schema/data contract. Миграции не удаляют мир и не сбрасывают player coins, ownership, relations, events или существующее состояние объектов. DB из более новой неизвестной версии отклоняется с typed error вместо рискованного downgrade.

Проверить апгрейд representative legacy DB:

```bash
python scripts/demo_migration.py
```

## Natural-language intent provider

`/act` теперь имеет два уровня интерпретации:

1. точная grammar (`взять stone_flat_1`, `идти village_square` и т. п.) всегда проверяется первой и не требует AI;
2. если точная grammar не подошла и явно задан `OLLAMA_MODEL`, обычная фраза передаётся optional semantic provider.

LLM получает только компактный canonical context: текущую локацию, доступные выходы, видимых actors/entities, inventory и баланс. Его structured proposal ещё раз локально проверяется по allow-list текущего контекста и только после этого превращается в `CanonicalAction`. Любой выдуманный ID, неподдерживаемая механика или ошибка провайдера не создаёт gameplay event и не меняет каноническое состояние.

Для локального Ollama runtime:

```bash
export OLLAMA_MODEL='<имя уже установленной локальной модели>'
export OLLAMA_URL='http://127.0.0.1:11434'       # необязательно
export OLLAMA_TIMEOUT_SECONDS='5'                # необязательно, максимум 30
python -m samseberpg.discord_bot
```

Если `OLLAMA_MODEL` не задан, Discord build продолжает работать только на deterministic grammar.

Проверить semantic integration без сети и без притворного LLM-вызова:

```bash
python scripts/demo_natural_language.py
```

Этот demo использует deterministic fake resolver только для проверки контракта `natural phrase -> proposal -> context guard -> GameService`. В текущей среде разработки бинарник/model Ollama отсутствует, поэтому реальная inference здесь не заявляется как проверенная.
