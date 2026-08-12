from __future__ import annotations

import argparse
import os
from pathlib import Path

from .db import GameDatabase
from .game import GameService
from .llm_parser import OllamaActionParser, OllamaParserError, build_parser_context
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


def resolve_player_input(
    text: str,
    db: GameDatabase,
    ollama_parser: OllamaActionParser | None = None,
    player_id: str = "player_1",
):
    action = parse_command(text, player_id=player_id)
    if action is not None or ollama_parser is None:
        return action
    context = build_parser_context(db, player_id)
    return ollama_parser.parse(text, context, player_id=player_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sam-Sebe-RPG Pilot v0.1")
    parser.add_argument("--db", default="game.db", help="Путь к SQLite-файлу мира")
    parser.add_argument("--seed", type=int, default=1, help="Seed детерминированного RNG")
    parser.add_argument(
        "--ollama-model",
        default=os.environ.get("SAM_SEBE_OLLAMA_MODEL"),
        help="Опциональная локальная Ollama-модель для свободного ввода",
    )
    parser.add_argument(
        "--ollama-url",
        default=os.environ.get("SAM_SEBE_OLLAMA_URL", "http://localhost:11434"),
        help="Base URL локального Ollama",
    )
    args = parser.parse_args(argv)

    db = GameDatabase(Path(args.db))
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=args.seed)
    ollama_parser = (
        OllamaActionParser(model=args.ollama_model, base_url=args.ollama_url)
        if args.ollama_model
        else None
    )

    print("Sam-Sebe-RPG Pilot v0.1")
    _print_state(db)
    print("Напиши help для списка команд.")
    if ollama_parser is not None:
        print(
            f"Свободный ввод: Ollama {args.ollama_model} "
            "(parser только предлагает CanonicalAction)."
        )

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

        try:
            action = resolve_player_input(text, db, ollama_parser)
        except OllamaParserError as exc:
            print(f"Ollama parser недоступен: {exc}")
            continue
        if action is None:
            if ollama_parser is None:
                print(
                    "Не понял действие. Попробуй базовую команду или запусти CLI "
                    "с --ollama-model для свободного ввода."
                )
            else:
                print("Это намерение пока нельзя выразить текущим игровым языком.")
            continue

        result = game.execute(action)
        print(result.summary)
        if result.data:
            if "entities" in result.data:
                exits = result.data.get("exits", [])
                print("Выходы: " + (", ".join(exits) if exits else "нет"))
                entities = result.data["entities"]
                if entities:
                    print("Сущности:")
                    for entity in entities:
                        print(
                            f"  {entity['entity_id']} — {entity['name']} "
                            f"[{entity['entity_type']}]"
                        )
                else:
                    print("Сущности: нет")
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
