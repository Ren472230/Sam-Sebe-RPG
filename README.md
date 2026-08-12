# Sam-Sebe-RPG — Pilot v0.1

Минимальная рабочая модель **Emergent RPG / Living World**. Этот срез проверяет одну продуктовую гипотезу: интересно ли игроку экспериментировать с маленьким persistent-миром, если игра распознаёт устойчивое поведение и превращает его в персональную механику.

## Что уже работает

- persistent-мир в SQLite;
- 3 локации, 3 NPC, 2 ворона, предметы и цели;
- authoritative deterministic `GameService`;
- действия `LOOK`, `MOVE`, `TAKE`, `DROP`, `THROW`, `WAIT`;
- append-only `action_events`, включая неудачные попытки;
- rule-based Behavior Analyzer;
- защита от grind: одного повторения недостаточно для специализации;
- achievement **«Рука помнит дугу»**;
- ability **«Прицельный бросок»**: 45% → 55% точности;
- whitelist/limits для будущего Mechanic Compiler;
- простой русский/канонический parser;
- локальный CLI;
- детерминированный demo полного progression loop.

## Архитектурное правило

LLM не является источником истины мира.

```text
text / future LLM parser
        ↓
CanonicalAction
        ↓
validation
        ↓
GameService
        ↓
SQLite authoritative state + ActionEvent
        ↓
BehaviorAnalyzer
        ↓
ProgressionService
```

Любой будущий AI-компонент сможет только предложить структурированное действие или механику. Изменение состояния проходит обычный код и валидаторы.

## Быстрый запуск

Требуется Python 3.12+.

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

Тесты:

```bash
pytest -q
```

## Детерминированный vertical demo

```bash
python scripts/demo_pilot.py
```

Ожидаемый финал:

```text
aimed_throw: unlocked
aimed_accuracy: 55%
persistence: PASS
DEMO PASS
```

Demo специально ускоряет progression: 12 разнообразных бросков по 3 целям в 3 локациях двумя типами снарядов. При seed=1 достаточно попаданий для проверки компетентности.

## Играть вручную

После установки:

```bash
sam-sebe-rpg
```

Или без установки editable package:

```bash
PYTHONPATH=src python -m samseberpg.cli
```

Основные команды:

```text
осмотреться
идти village_square
взять stone_flat_1
бросить stone_flat_1 в target_barrel
прицельно бросить stone_flat_1 в target_barrel
бросить_на_землю stone_flat_1
ждать 3
help
quit
```

Состояние по умолчанию хранится в `game.db`, поэтому переживает перезапуск CLI.

## Первая progression rule

`aimed_throw` открывается, когда накоплено одновременно:

- минимум 12 валидных `THROW`;
- минимум 5 попаданий;
- минимум 3 разные цели;
- минимум 2 типа импровизированных снарядов;
- минимум 2 разные локации.

Это намеренно ускоренные thresholds для founder playtest. Они не являются будущим балансом игры.

## Mechanic safety boundary

Первый validator разрешает только известные примитивы, в том числе:

- `MODIFY_ACCURACY`;
- `MODIFY_RANGE`;
- `MODIFY_COST`;
- `MODIFY_QUALITY`;
- `MODIFY_RELATION_GAIN`;
- `UNLOCK_ACTION_VARIANT`;
- `CONDITIONAL_MODIFIER`;
- `REPUTATION_TAG`.

Например, `MODIFY_ACCURACY` ограничен максимум 15 процентными пунктами. Произвольное `+100 accuracy` отклоняется.

## Что сознательно пока отсутствует

- Discord bot;
- LLM parser;
- полноценные диалоги NPC;
- combat/PvP;
- квесты и классы;
- экономика и организации;
- сложная фоновая симуляция;
- multiplayer concurrency;
- web UI;
- RAG/vector DB;
- платная инфраструктура.

Это осознанный scope cut. Сначала локальная модель должна доказать, что сам цикл **Behavior → Achievement → Ability** вызывает желание экспериментировать.

## Следующий продуктовый milestone

Founder playtest: сыграть вручную 30–60 минут и фиксировать не количество реализованных механик, а количество самостоятельных «а что если…?» экспериментов, понятность причин появления способности и желание сразу проверить её границы.

Техническая спецификация и план находятся в `docs/superpowers/`.
