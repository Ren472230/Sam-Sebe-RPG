# Sam-Sebe RPG — Pilot v0.1

Экспериментальная living-world RPG, где **поведение игрока становится прогрессией**: мир фиксирует подтверждённые действия, распознаёт устойчивые паттерны и открывает новые игровые возможности без заранее выбранного класса.

Этот репозиторий пока содержит не «готовую игру», а проверяемое deterministic-ядро вертикального среза. Его задача — доказать главный цикл:

`Behavior → Evidence → Achievement → Ability → New mechanic`

## Что уже работает

- маленький persistent-мир в SQLite;
- 3 локации, 3 NPC, 2 ворона и простые предметы;
- authoritative deterministic simulation;
- действия `LOOK`, `MOVE`, `TAKE`, `DROP`, `THROW`, `WAIT`;
- append-only журнал всех результатов действий, включая ошибки;
- воспроизводимый RNG через seed;
- поведенческая аналитика бросков;
- анти-гринд правило: повторение одного действия само по себе не открывает навык;
- достижение `hand_remembers_arc`;
- способность `aimed_throw` (+10 процентных пунктов к точности);
- whitelist/validator для разрешённых механических примитивов;
- простой русскоязычный deterministic parser;
- локальный CLI и воспроизводимый demo-сценарий;
- persistence прогрессии после перезапуска.

## Архитектурное правило

Только deterministic simulation изменяет каноническое состояние мира.

```text
text / UI / Discord / LLM
        ↓
parsed proposal
        ↓
CanonicalAction
        ↓
validation + deterministic resolver
        ↓
SQLite transaction + ActionEvent
        ↓
BehaviorAnalyzer
        ↓
ProgressionService
```

LLM в будущих версиях может понимать намерение, вести диалоги, писать narrative output и предлагать механику, но не получает прямого права изменять деньги, предметы, отношения, достижения или историю мира.

## Быстрый старт

Требуется Python 3.12+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
python -m pip install -e '.[dev]'
pytest -q
sam-sebe-rpg
```

Однокомандный режим:

```bash
sam-sebe-rpg --command "осмотреться"
sam-sebe-rpg --command "взять stone_flat_1"
```

## Команды Pilot v0.1

```text
осмотреться
идти <location_id>
взять <item_id>
оставить <item_id>
бросить <item_id> в <target_id>
прицельно бросить <item_id> в <target_id>
ждать [ticks]
help
quit
```

## Полная демонстрация progression loop

```bash
python scripts/demo_pilot.py --db demo-pilot.db
```

Ожидаемый финал:

```text
ACHIEVEMENTS: hand_remembers_arc
ABILITIES: aimed_throw
AIMED THROW: ... chance=55%
DEMO PASS
```

## Почему первый UI — CLI

CLI — только test harness для ядра. Продуктовое направление проекта — **визуальная новелла в единой premium ASCII/символьной эстетике**: персонажи, локации, диалоговое окно, RPG-меню, эффекты и цвет работают в одном визуальном языке. Игровая поверхность должна подключаться как адаптер и не дублировать правила simulation core.

## Что сознательно не входит в Pilot v0.1

- полноценный Discord-адаптер;
- multiplayer concurrency;
- LLM parser/dialogue provider;
- автономная симуляция NPC в реальном времени;
- утренняя газета мира;
- Закон Забвения / долгосрочное сжатие памяти;
- экономика, бизнесы и недвижимость игроков;
- готовый VN/ASCII presentation layer;
- фиксированные классы, уровни и заранее заполненные деревья навыков.

Эти подсистемы добавляются только после сохранения главного инварианта: **канонический мир принадлежит детерминированной симуляции и базе данных, а не LLM**.
