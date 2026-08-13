from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass
from pathlib import Path

from .day import DayService
from .db import GameDatabase
from .domain import CanonicalAction
from .game import GameService
from .llm_parser import OllamaActionParser, OllamaParserError, build_parser_context
from .parser import parse_command


INTRO = """
Ты новенький в маленьком поселении у брода. Утро только началось.
Денег у тебя нет, и место на ночь пока не найдено. Люди вокруг живут своей жизнью.
Ты можешь осмотреться и пробовать делать то, что кажется тебе разумным или интересным.
""".strip()


def render_help(mode: str, *, has_aimed: bool, ollama_enabled: bool) -> str:
    if mode == "founder":
        input_hint = (
            "Пиши обычным языком, что хочешь попробовать сделать."
            if ollama_enabled
            else "Пиши действие; эта сборка без Ollama понимает ограниченный язык команд."
        )
        lines = [
            "Подсказка:",
            f"  {input_hint}",
            "  осмотреться — сориентироваться вокруг",
            "  help — эта подсказка",
            "  quit — выйти",
        ]
        if has_aimed:
            lines.append("  Ты освоил прицельный бросок — можешь описать, что целишься особенно тщательно.")
        return "\n".join(lines)

    if mode != "systems":
        raise ValueError(f"Unknown CLI mode: {mode}")

    lines = [
        "Команды:",
        "  осмотреться",
        "  идти <location_id>",
        "  взять <item_id>",
        "  бросить_на_землю <item_id>",
        "  поговорить <npc_id>",
        "  спросить <npc_id> о ночлеге",
        "  оплатить ночлег",
        "  попросить ночлег",
        "  дать <item_id> <npc_id>",
        "  покормить <animal_id> <item_id>",
        "  бросить <item_id> в <target_id>",
    ]
    if has_aimed:
        lines.append("  прицельно бросить <item_id> в <target_id>")
    lines.extend(["  ждать [ticks]", "  help", "  quit"])
    return "\n".join(lines)


# Compatibility alias for existing imports; deliberately does not reveal locked aimed syntax.
HELP = render_help("systems", has_aimed=False, ollama_enabled=False)


@dataclass(frozen=True, slots=True)
class InputResolution:
    action: CanonicalAction | None
    attempt_id: int
    parser_mode: str
    parser_model: str | None
    parser_error: str | None
    latency_ms: float


def _print_state(db: GameDatabase, player_id: str = "player_1") -> None:
    player = db.fetch_player(player_id)
    if player is None:
        print("Игрок не найден.")
        return

    world_time = db.get_world_time()
    resources = db.fetch_player_resources(player_id) or {
        "coins": 0,
        "lodging_secured": False,
    }
    phase = DayService().phase(world_time)
    print(f"Локация: {player['location_id']} | {phase} | Время: {world_time}")
    lodging = "есть" if resources["lodging_secured"] else "нет"
    print(f"Монеты: {resources['coins']} | Ночлег: {lodging}")
    inventory = db.list_inventory(player_id)
    print("Инвентарь: " + (", ".join(inventory) if inventory else "пуст"))


def _canonical_action_payload(action: CanonicalAction | None) -> dict[str, object] | None:
    if action is None:
        return None
    return {
        "actor_id": action.actor_id,
        "action_type": action.action_type.value,
        "target_id": action.target_id,
        "item_id": action.item_id,
        "destination_id": action.destination_id,
        "modifiers": dict(action.modifiers),
        "source_text": action.source_text,
    }


def resolve_player_input(
    text: str,
    db: GameDatabase,
    ollama_parser: OllamaActionParser | None = None,
    player_id: str = "player_1",
):
    """Compatibility parser API without telemetry side effects."""
    action = parse_command(text, player_id=player_id)
    if action is not None or ollama_parser is None:
        return action
    context = build_parser_context(db, player_id)
    return ollama_parser.parse(text, context, player_id=player_id)


def resolve_and_record_player_input(
    text: str,
    db: GameDatabase,
    ollama_parser: OllamaActionParser | None = None,
    player_id: str = "player_1",
) -> InputResolution:
    started = time.perf_counter()
    parser_mode = "deterministic"
    parser_model: str | None = None
    parser_error: str | None = None

    action = parse_command(text, player_id=player_id)
    if action is None:
        if ollama_parser is None:
            parser_mode = "none"
        else:
            parser_mode = "ollama"
            parser_model = ollama_parser.model
            try:
                context = build_parser_context(db, player_id)
                action = ollama_parser.parse(text, context, player_id=player_id)
            except OllamaParserError as exc:
                parser_error = str(exc)
                action = None

    latency_ms = (time.perf_counter() - started) * 1000.0
    attempt_id = db.record_input_attempt(
        world_time=db.get_world_time(),
        raw_text=text,
        parser_mode=parser_mode,
        parser_model=parser_model,
        recognized=action is not None,
        canonical_action=_canonical_action_payload(action),
        parser_error=parser_error,
        latency_ms=latency_ms,
    )
    return InputResolution(
        action=action,
        attempt_id=attempt_id,
        parser_mode=parser_mode,
        parser_model=parser_model,
        parser_error=parser_error,
        latency_ms=latency_ms,
    )


def _render_result(result) -> None:
    print(result.summary)
    if "entities" in result.data:
        exits = result.data.get("exits", [])
        print("Выходы: " + (", ".join(exits) if exits else "нет"))
        entities = result.data["entities"]
        if entities:
            for entity in entities:
                print(
                    f"  {entity['entity_id']} — {entity['name']} "
                    f"[{entity['entity_type']}]"
                )
        else:
            print("Сущности: нет")
    if "hit" in result.data:
        outcome = "попадание" if result.data["hit"] else "промах"
        print(f"Бросок: {outcome}; шанс {result.data['accuracy']:.0%}.")
    observed = result.data.get("observed_world_events", [])
    if isinstance(observed, list):
        for event in observed:
            if isinstance(event, dict) and event.get("summary"):
                print(str(event["summary"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sam-Sebe-RPG Pilot v0.1")
    parser.add_argument("--db", default="game.db", help="Путь к SQLite-файлу мира")
    parser.add_argument("--seed", type=int, default=1, help="Seed детерминированного RNG")
    parser.add_argument(
        "--mode",
        choices=("founder", "systems"),
        default="founder",
        help="founder скрывает каталог механик; systems показывает канонические команды",
    )
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
    print(INTRO)
    _print_state(db)
    print("Напиши help, если нужна подсказка.")
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
            print(
                render_help(
                    args.mode,
                    has_aimed=db.has_ability("player_1", "aimed_throw"),
                    ollama_enabled=ollama_parser is not None,
                )
            )
            continue

        resolution = resolve_and_record_player_input(text, db, ollama_parser)
        if resolution.parser_error is not None:
            print(f"Ollama parser недоступен: {resolution.parser_error}")
            continue
        action = resolution.action
        if action is None:
            if ollama_parser is None:
                print(
                    "Не понял действие. В founder-режиме каталог возможностей специально скрыт; "
                    "попробуй сформулировать проще или подключи --ollama-model."
                )
            else:
                print("Это намерение пока нельзя выразить текущим игровым языком.")
            continue

        result = game.execute(action)
        db.complete_input_attempt(resolution.attempt_id, result.code)
        _render_result(result)

        has_aimed = db.has_ability("player_1", "aimed_throw")
        if has_aimed and not known_aimed:
            print("\n★ Достижение: «Рука помнит дугу»")
            print("★ Новая способность: «Прицельный бросок» (+10 п.п. точности)")
            if args.mode == "founder":
                print("Теперь ты можешь особенно тщательно прицеливаться перед броском.\n")
            else:
                print("Команда: прицельно бросить <item_id> в <target_id>\n")
        known_aimed = has_aimed
        _print_state(db)


if __name__ == "__main__":
    raise SystemExit(main())
