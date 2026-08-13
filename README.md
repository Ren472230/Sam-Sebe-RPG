# Sam-Sebe-RPG — Pilot v0.1

Экспериментальная маленькая модель **Emergent RPG / Living World**.

Текущий Pilot проверяет три связанные гипотезы:

1. интересно ли игроку самостоятельно экспериментировать в маленьком системном мире без класса и quest checklist;
2. создаёт ли автономная жизнь NPC ощущение, что мир занят своими делами;
3. воспринимается ли `Behavior → Achievement → Ability` как естественная биографическая прогрессия.

Автотесты доказывают техническое поведение. Интересность игры подтверждает только реальный founder playtest.

## Старт

Игрок приезжает в маленькое поселение у брода:

- утро;
- 0 монет;
- профессии нет;
- ночлег не найден;
- место у Орена стоит 3 монеты или может быть получено через доверие местного;
- решать вопрос ночлега необязательно.

Это мягкая жизненная ситуация, а не квест.

## Что уже работает

### Authoritative world

- persistent SQLite;
- schema version 2 + migration pre-audit saves;
- 3 локации, 3 NPC, 2 ворона;
- `LOOK / MOVE / TAKE / DROP / TALK / GIVE / FEED / THROW / WAIT`;
- deterministic persistent RNG;
- `GameService` остаётся единственной authoritative gameplay boundary;
- `action_events`, `world_events` и `input_attempts` разделены по назначению.

### Living World v0

Мира и Каспар имеют минимальную автономную причинную цепочку без LLM:

```text
Мира работает
→ расходует wood_stock
→ возникает нехватка
→ просит ресурс
→ Каспар реагирует
→ забирает реальную driftwood_1
→ возвращается
→ передаёт древесину
→ Мира снова может работать
```

Игрок и NPC используют **тот же физический предмет**. Если игрок забрал `driftwood_1` первым, Каспар не создаёт замену из воздуха.

`WAIT N` обрабатывает каждый промежуточный tick. Автономные события пишутся в `world_events` и не загрязняют Behavior Engine игрока.

После действия обычный интерфейс показывает только новые автономные события, которые произошли **в текущей локации игрока**. Off-screen события сохраняются в истории мира, но не выдаются игроку как omniscient debug log.

### Первый день и отношения

Текущий Pilot balance:

```text
Mira: flat_stone  -> +1 trust, +1 coin
Mira: round_stone -> +1 trust, +1 coin
Mira: useful_wood -> +1 trust, +0 coins
Kaspar: pinecone  -> +1 trust, +1 coin
```

Повтор того же contribution tag не фармит деньги/доверие.

Социальный ночлег доступен, когда Mira или Kaspar имеют trust >= 2. Поэтому два разных стартовых вклада дают социальный маршрут, но только 2 монеты — денежный путь за 3 монеты требует ещё одного взаимодействия/исследования.

### Последствия очевидных действий

- кормление ворона повышает его trust;
- попадание в вывеску Орена снижает его trust;
- успешный бросок в NPC снижает trust цели и сохраняет `hit_by_player_count`;
- успешный бросок в ворона повышает fear, снижает trust и заставляет его улететь;
- combat/HP при этом не добавлены.

### Behavior → Achievement → Ability

Первая скрытая ветка:

```text
разнообразное компетентное метание
→ «Рука помнит дугу»
→ aimed_throw
```

`aimed_throw` добавляет +10 процентных пунктов точности после persisted `MechanicValidator` проверки.

У способности теперь есть один положительный системный use case: прицельное попадание в старую бочку во дворе мастерской может один раз выправить перекошенную деталь; Мира замечает точную работу и повышает trust. Это не квест и не новая ветка контента — только доказательство, что emergent ability способна иметь практический смысл.

## Архитектурное правило LLM

LLM не определяет реальность мира.

```text
raw player input
    ↓
deterministic parser / optional Ollama fallback
    ↓
CanonicalAction proposal
    ↓
GameService validation + deterministic resolution
    ↓
time advance + Living World reaction
    ↓
SQLite authoritative state
    ↓
action/world evidence + Behavior/Progression
```

Ollama никогда не пишет в SQLite и не выбирает исход действия.

## Input telemetry

Schema v2 добавляет `input_attempts`. Для каждой игровой фразы локально сохраняются:

- raw input;
- parser mode;
- parser model;
- recognition status;
- proposed canonical action;
- GameService result code;
- parser error;
- parser latency.

Эта телеметрия **не влияет на игровой мир**.

Human playtest report показывает только агрегаты, а не сырой текст игрока. Это позволяет измерять parser friction, включая попытки, которые вообще не дошли до `GameService`.

## Action timing contract

Для новых action events:

- `world_time` = completion/resolved tick;
- `started_at_tick` = начало;
- `resolved_at_tick` = завершение;
- `duration_ticks` = сколько tick заняло действие.

`LOOK` и неуспешные действия имеют duration 0. Обычные успешные timed actions — 1. `WAIT N` — N.

Pre-audit saves мигрируют в schema v2 без сброса state; старым events duration консервативно ставится 0, потому что историческую длительность нельзя восстановить надёжно.

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
python -m compileall -q src scripts
pytest -q
```

## Два CLI-режима

### Founder — продуктовый режим

```bash
sam-sebe-rpg --mode founder --db playtests/founder-free.db --ollama-model <model>
```

Это режим по умолчанию. `help` сознательно **не показывает каталог игровых механик и locked abilities**, чтобы не загрязнять `WHAT_IF` experiment подсказками интерфейса.

### Systems — диагностический режим

```bash
sam-sebe-rpg --mode systems --db playtests/founder-systems.db
```

Показывает канонические команды для технической проверки. Синтаксис `aimed_throw` появляется только после реального unlock.

Systems mode не используется для доказательства ощущения свободного ввода.

## Свободный ввод через Ollama

```bash
sam-sebe-rpg \
  --mode founder \
  --db playtests/founder-free.db \
  --ollama-model <локальная_модель>
```

Также поддерживаются:

```bash
export SAM_SEBE_OLLAMA_MODEL=<локальная_модель>
export SAM_SEBE_OLLAMA_URL=http://localhost:11434
```

Structured parser ограничен реализованными action types, canonical lodging topics и authoritative entity IDs текущего контекста.

Тесты с fake transport доказывают schema/validation boundary, но не качество конкретной реальной модели. Это проверяется только founder free-input session.

## Demos

### Progression

```bash
python scripts/demo_pilot.py
```

Доказывает технический `behavior → achievement → ability → persistence` loop.

### Первый день — денежный маршрут

```bash
python scripts/demo_first_day.py --db first-day-demo.db
```

После аудита третий coin требует выйти из стартового двора и взаимодействовать с Каспаром; два стартовых камня больше не покупают комнату автоматически.

### Living World

```bash
python scripts/demo_living_world.py --db living-world-demo.db
```

Доказывает автономную цепочку Миры/Каспара и persistence через reopen.

### Founder readiness

```bash
python scripts/demo_founder_readiness.py --db founder-ready.db
```

Smoke проверяет в одной persistent session:

- spoiler-safe founder help;
- input telemetry;
- локально наблюдаемое автономное событие;
- audited social route;
- hostile consequence;
- positive aimed utility;
- schema v2.

Это **не** доказательство fun/product-market fit.

## Playtest report

```bash
python scripts/playtest_report.py playtests/founder-free.db
python scripts/playtest_report.py playtests/founder-free.db --json
```

Отчёт показывает:

- player action counts/failures;
- input-attempt recognition metrics;
- parser mode/error aggregates;
- throwing evidence;
- achievements/abilities;
- world time/day phase;
- coins/lodging;
- NPC/animal trust;
- counts/latest autonomous world events.

Протокол: `docs/playtests/founder-v0.1.md`.

## CI

`.github/workflows/ci.yml` проверяет feature-ветку и PR на Python 3.12:

```text
editable install
compileall
pytest
```

## Что сознательно НЕ делаем сейчас

- quest/task log;
- classes/levels;
- combat/HP;
- hunger/thirst;
- crafting;
- shops/full economy;
- LLM NPC dialogue/agency;
- factions/organizations/romance;
- more NPCs/locations/items;
- Discord/web UI;
- multiplayer concurrency;
- RAG/vector DB;
- generic GOAP/utility planner;
- resource respawn/economy;
- generic Mechanic Compiler;
- real-time catch-up while the program is closed.

## Следующий product gate

Не расширять мир до Living World v1.

Следующее доказательство — **реальный 30–60 минутный founder free-input playtest**. После него решение принимается по evidence: parser friction, самостоятельные `WHAT_IF`, заметность причинных world events, желание вмешиваться, ценность последствий и biographical progression.