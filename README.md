# Sam-Sebe-RPG — Pilot v0.1

Первая маленькая игровая модель **Emergent RPG / Living World**.

Сейчас Pilot проверяет уже не только технический цикл `Behavior → Achievement → Ability`, но и более важный вопрос:

> интересно ли игроку жить и экспериментировать в маленьком системном мире, если у него есть понятная жизненная ситуация, но нет класса, квестового списка и заданного маршрута?

## Как начинается игра

Ты приезжаешь в маленькое поселение у брода.

- утро;
- денег нет;
- профессии нет;
- ночлег пока не найден;
- к вечеру можно попробовать решить вопрос с ночлегом, но игра не заставляет это делать.

У трактирщика Орена место стоит 3 монеты. Есть и социальный путь: если кто-то из местных достаточно тебе доверяет, можно попросить ночлег без оплаты.

Это **мягкая мотивация**, а не квест. Игрок может вообще проигнорировать ночлег и заниматься тем, что ему интересно.

## Что уже работает

- persistent-мир в SQLite;
- 3 локации, 3 NPC, 2 ворона;
- время суток и ленивое расписание NPC;
- монеты и persistent-состояние ночлега;
- `LOOK`, `MOVE`, `TAKE`, `DROP`, `TALK`, `GIVE`, `FEED`, `THROW`, `WAIT`;
- deterministic social rules и доверие;
- подарки с защитой от бесконечного фарма одной и той же находки;
- кормление воронов с persistent trust;
- последствия: попадание в вывеску трактира ухудшает отношение Орена;
- два реальных пути к ночлегу: деньги или доверие;
- append-only `ActionEvent` log;
- Behavior Analyzer;
- скрытая progression **«Рука помнит дугу» → `aimed_throw`**;
- `MechanicValidator` с whitelist/limits;
- deterministic parser;
- опциональный локальный Ollama parser со structured output;
- локальный CLI;
- offline playtest report;
- два demo: технический progression-loop и игровой «первый день».

## Главное архитектурное правило

LLM не определяет реальность мира.

```text
текст игрока
    ↓
parser / optional Ollama
    ↓
CanonicalAction proposal
    ↓
GameService validation + deterministic rules
    ↓
SQLite authoritative state + ActionEvent
    ↓
BehaviorAnalyzer / ProgressionService
```

Даже в режиме свободного ввода Ollama не пишет в SQLite и не решает исход действия.

## Быстрый запуск

Нужен Python 3.12+.

```bash
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Установка:

```bash
pip install -e ".[dev]"
```

Проверка:

```bash
pytest -q
```

## Играть вручную

```bash
sam-sebe-rpg --db game.db
```

или:

```bash
PYTHONPATH=src python -m samseberpg.cli --db game.db
```

Начало не показывает оптимальный путь. Для systems-only режима можно использовать `help` и `осмотреться`.

Примеры канонических команд:

```text
осмотреться
идти village_square
взять stone_flat_1
поговорить mira_craftswoman
дать stone_flat_1 mira_craftswoman
покормить raven_1 bread_1
спросить oren_innkeeper о ночлеге
оплатить ночлег
попросить ночлег
бросить stone_flat_1 в target_barrel
прицельно бросить stone_flat_1 в target_barrel
ждать 3
```

`спросить ... о ночлеге` **только узнаёт условия**. Деньги не списываются без отдельного `оплатить ночлег`. Социальный вариант тоже требует отдельного `попросить ночлег`.

## Свободный ввод через Ollama

Для продуктового теста свободной формулировки действий:

```bash
sam-sebe-rpg --db playtests/founder-free.db --ollama-model <локальная_модель>
```

Также можно задать:

```bash
export SAM_SEBE_OLLAMA_MODEL=<локальная_модель>
export SAM_SEBE_OLLAMA_URL=http://localhost:11434
```

Ollama ограничен JSON Schema и authoritative world IDs. Для разговоров о ночлеге разрешены только канонические намерения:

- `lodging` — узнать условия;
- `pay_lodging` — явно заплатить;
- `request_lodging` — явно попросить по доверию.

Произвольные action/topic или выдуманные ID отбрасываются.

## Два demo

### 1. Старый технический progression-loop

```bash
python scripts/demo_pilot.py
```

Проверяет полный цикл:

```text
behavior → achievement → aimed_throw → persistence
```

Финал:

```text
aimed_throw: unlocked
aimed_accuracy: 55%
persistence: PASS
DEMO PASS
```

### 2. Первый игровой день

```bash
python scripts/demo_first_day.py --db first-day-demo.db
```

Показывает **один возможный**, но не обязательный маршрут: взаимодействие с Мирой, вороном и Ореном, получение монет и явную оплату ночлега.

Финал:

```text
lodging_secured=True
raven_trust=1
FIRST DAY DEMO PASS
```

## Первый день: системные правила

### Время

- tick 0–3 — утро;
- tick 4–7 — день;
- tick 8–11 — под вечер;
- tick 12+ — вечер.

`LOOK` не тратит время. Большинство успешных действий тратят 1 tick. `WAIT` тратит указанное число ticks.

К более позднему времени Мира и Каспар самостоятельно перемещаются на площадь. Это lazy simulation: мир меняется при обработке следующего действия, без постоянного фонового сервера.

### Доверие

Для Pilot механически важно только `trust`:

- 0 — незнакомец;
- 1–2 — положительное знакомство;
- 3+ — человек готов поручиться за игрока;
- отрицательное значение — недоверие.

### Мини-экономика

Это ещё не полноценная экономика. Монеты нужны только как альтернативный путь к ночлегу.

Полезные **первые уникальные** находки могут дать монеты/доверие. Повтор одного и того же типа находки не создаёт бесконечный доход.

## Behavior → Achievement → Ability

Существующая бросковая ветка остаётся скрытой и необязательной.

`aimed_throw` открывается при сочетании:

- минимум 12 валидных бросков;
- минимум 5 попаданий;
- минимум 3 разных целей;
- минимум 2 типов импровизированных снарядов;
- минимум 2 локаций.

Это ускоренные условия для Pilot, а не будущий баланс.

## Playtest report

После ручной сессии:

```bash
python scripts/playtest_report.py game.db
```

или JSON:

```bash
python scripts/playtest_report.py game.db --json
```

Отчёт показывает:

- число событий/ошибок;
- типы действий и локации;
- throwing evidence;
- achievements/abilities;
- время/фазу дня;
- монеты и статус ночлега;
- trust NPC;
- trust животных.

Эти цифры дополняют наблюдение, но не заменяют главный продуктовый сигнал: **сколько раз игрок сам подумал «а что будет, если…?»**

Точный протокол: `docs/playtests/founder-v0.1.md`.

## Что сознательно НЕ делаем сейчас

- quest/task log;
- классы и уровни;
- combat/PvP;
- hunger/thirst/health;
- crafting;
- магазины и полноценную экономику;
- LLM-диалоги NPC;
- factions/organizations/romance;
- Discord;
- multiplayer concurrency;
- web UI;
- RAG/vector DB;
- больше локаций и NPC;
- вторую большую progression branch.

Сначала один маленький день должен доказать, что сочетание **мотив → эксперимент → системное последствие → персональная история/прогрессия** действительно интересно.
