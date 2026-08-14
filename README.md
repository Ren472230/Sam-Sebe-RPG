# Sam-Sebe-RPG — Emergent RPG / Living World

Экспериментальная multiplayer-first текстовая RPG с одним общим persistent-миром. Каноническое состояние хранится в SQLite; Discord и будущий LLM-слой являются адаптерами и не могут менять состояние напрямую.

## Что уже реализовано в Shared World Kernel

- одна деревня: 3 локации, 3 NPC, 12 стартовых объектов;
- несколько игроков в одном каноническом мире;
- Discord user ID -> стабильный player actor;
- LOOK / MOVE / TAKE / DROP / THROW / GIVE;
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

Сейчас намеренно отсутствуют combat, crafting, большой мир, dynamic lighting, автономные LLM-NPC, vector DB/RAG, PostgreSQL/Redis и Discord Activity. Discord adapter, THROW/GIVE и persistent consequences уже есть. Следующий продуктовый слой — USE/BUY и минимальный экономический loop.

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
- `/act text:дать bread_1 npc_oren`.

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
