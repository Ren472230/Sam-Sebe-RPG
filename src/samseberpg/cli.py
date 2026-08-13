from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .db import GameDatabase
from .domain import ActionResult
from .game import GameService
from .parser import parse_command

HELP_TEXT = """Команды:
  осмотреться
  идти <location_id>
  взять <item_id>
  оставить <item_id>
  бросить <item_id> в <target_id>
  прицельно бросить <item_id> в <target_id>
  ждать [ticks]
  help
  quit
"""


def render_result(result: ActionResult) -> str:
    lines = [result.summary]
    entities = result.data.get("entities")
    if isinstance(entities, list):
        for entity in entities:
            lines.append(f"  - {entity['name']} [{entity['entity_id']}]")
    unlocked = result.data.get("unlocked")
    if isinstance(unlocked, list) and unlocked:
        lines.append("Открыто: " + ", ".join(str(item) for item in unlocked))
    if "hit" in result.data:
        outcome = "попадание" if result.data["hit"] else "промах"
        chance = float(result.data.get("accuracy_chance", 0))
        lines.append(f"  {outcome}; шанс {chance:.0%}")
    return "\n".join(lines)


def _execute_text(game: GameService, text: str) -> tuple[int, str]:
    action = parse_command(text)
    if action is None:
        return 2, "Команда не распознана. Введите help для списка команд."
    result = game.execute(action)
    return (0 if result.success else 1), render_result(result)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sam-Sebe RPG Pilot v0.1")
    parser.add_argument("--db", default="game.db", help="Путь к SQLite-файлу мира")
    parser.add_argument("--seed", type=int, default=0, help="Seed детерминированного RNG")
    parser.add_argument("--command", help="Выполнить одну команду и завершиться")
    args = parser.parse_args(list(argv) if argv is not None else None)

    db = GameDatabase(Path(args.db))
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=args.seed)

    if args.command is not None:
        code, output = _execute_text(game, args.command)
        print(output)
        return code

    print("Sam-Sebe RPG — Pilot v0.1")
    print("Детерминированный living-world core. Введите help для команд.\n")
    _, opening = _execute_text(game, "осмотреться")
    print(opening)

    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nДо встречи.")
            return 0

        if not text:
            continue
        lowered = text.casefold()
        if lowered in {"quit", "exit", "выход"}:
            print("До встречи.")
            return 0
        if lowered in {"help", "помощь", "?"}:
            print(HELP_TEXT)
            continue

        _, output = _execute_text(game, text)
        print(output)


if __name__ == "__main__":
    raise SystemExit(main())
