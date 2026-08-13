from __future__ import annotations

from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType
from samseberpg.llm_parser import OllamaActionParser, OllamaParserError


def make_db(tmp_path: Path) -> GameDatabase:
    db = GameDatabase(tmp_path / "audit-cli.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db


def test_founder_help_hides_action_catalogue_and_locked_ability() -> None:
    from samseberpg.cli import render_help

    text = render_help("founder", has_aimed=False, ollama_enabled=True).lower()

    assert "осмотреться" in text
    assert "help" in text
    assert "quit" in text
    assert "покормить <animal_id>" not in text
    assert "дать <item_id>" not in text
    assert "прицельно бросить" not in text


def test_systems_help_lists_canonical_commands_but_hides_locked_ability() -> None:
    from samseberpg.cli import render_help

    locked = render_help("systems", has_aimed=False, ollama_enabled=False)
    unlocked = render_help("systems", has_aimed=True, ollama_enabled=False)

    assert "покормить <animal_id> <item_id>" in locked
    assert "дать <item_id> <npc_id>" in locked
    assert "прицельно бросить" not in locked
    assert "прицельно бросить <item_id> в <target_id>" in unlocked


def test_deterministic_input_is_recorded_once_and_completed(tmp_path: Path) -> None:
    from samseberpg.cli import resolve_and_record_player_input
    from samseberpg.game import GameService

    db = make_db(tmp_path)
    game = GameService(db, seed=1)

    resolution = resolve_and_record_player_input("осмотреться", db)
    assert resolution.action is not None
    assert resolution.action.action_type == ActionType.LOOK
    result = game.execute(resolution.action)
    db.complete_input_attempt(resolution.attempt_id, result.code)

    attempts = db.list_input_attempts()
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["parser_mode"] == "deterministic"
    assert attempt["recognized"] is True
    assert attempt["canonical_action"]["action_type"] == "LOOK"
    assert attempt["result_code"] == "OK"


def test_unrecognized_input_without_ollama_is_still_recorded(tmp_path: Path) -> None:
    from samseberpg.cli import resolve_and_record_player_input

    db = make_db(tmp_path)
    resolution = resolve_and_record_player_input("попробую свистнуть старую мелодию", db)

    assert resolution.action is None
    attempts = db.list_input_attempts()
    assert len(attempts) == 1
    assert attempts[0]["parser_mode"] == "none"
    assert attempts[0]["recognized"] is False
    assert attempts[0]["canonical_action"] is None


def test_ollama_parser_error_is_recorded_without_losing_input(tmp_path: Path) -> None:
    from samseberpg.cli import resolve_and_record_player_input

    db = make_db(tmp_path)

    def broken_transport(_url: str, _payload: dict[str, object], _timeout: float):
        raise OllamaParserError("local model unavailable")

    parser = OllamaActionParser(model="fake-local", transport=broken_transport)
    resolution = resolve_and_record_player_input("попробую свистнуть старую мелодию", db, parser)

    assert resolution.action is None
    assert resolution.parser_error is not None
    attempts = db.list_input_attempts()
    assert len(attempts) == 1
    assert attempts[0]["parser_mode"] == "ollama"
    assert attempts[0]["parser_model"] == "fake-local"
    assert attempts[0]["recognized"] is False
    assert "local model unavailable" in attempts[0]["parser_error"]
