from __future__ import annotations

import argparse
from pathlib import Path

from .db import GameDatabase
from .game import GameService
from .parser import parse_command


HELP = """Команды:
  осмотреться
  идти <location_id>
  взять <item_id>
  бросить_на_землю <item_id>
  бросить <item_id> в <target_id>
  прицельно бросить <item_id> в <target_id>
  ждать [ticks]
  help
  quit
"""


def _print_state(db: GameDatabase, player_id: str = "player_1") -> None:
    player = db.fetch_player(player_id)
    if player is None:
        print("Игрок не найден.")
        return
    print(f"Локация: {player['location_id']} | Время: {db.get_world_time()}")
    inventory = db.list_inventory(player_id)
    print("Инвентарь: " + (", ".join(inventory) if inventory else "пуст"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sam-Sebe-RPG Pilot v0.1")
    parser.add_argument("--db", default="game.db", help="Путь к SQLite-файлу мира")
    parser.add_argument("--seed", type=int, default=1, help="Seed детерминированного RNG")
    args = parser.parse_args(argv)

    db = GameDatabase(Path(args.db))
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=args.seed)

    print("Sam-Sebe-RPG Pilot v0.1")
    _print_state(db)
    print("Напиши help для списка команд.")

    known_aimed = db.has_ability("player_1", "aimed_throw")
    while True:
        try:
            text = input("> ").strip()
        except EOFError:
            print()
            return 0

        if not text:
            continue
        if text.lower() in {"quit", "exit", "выход"}:
            return 0
        if text.lower() in {"help", "помощь"}:
            print(HELP)
            continue

        action = parse_command(text)
        if action is None:
            print("Не понял действие. Попробуй сформулировать его как одну из базовых команд.")
            continue

        result = game.execute(action)
        print(result.summary)
        if result.data:
            if "hit" in result.data:
                print(
                    f"Бросок: {'попадание' if result.data['hit'] else 'промах'}; "
                    f"шанс {result.data['accuracy']:.0%}."
                )

        has_aimed = db.has_ability("player_1", "aimed_throw")
        if has_aimed and not known_aimed:
            print("\n★ Достижение: «Рука помнит дугу»")
            print("★ Новая способность: «Прицельный бросок» (+10 п.п. точности)\n")
        known_aimed = has_aimed
        _print_state(db)


if __name__ == "__main__":
    raise SystemExit(main())
