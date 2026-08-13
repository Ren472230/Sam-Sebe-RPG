from __future__ import annotations

import json
from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType
from samseberpg.llm_parser import OllamaActionParser, build_parser_context


def test_build_parser_context_uses_authoritative_world_ids(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()

    context = build_parser_context(db, "player_1")

    assert context["location_id"] == "workshop_yard"
    assert context["exits"] == ["village_square"]
    assert context["inventory"] == []
    visible_ids = {entity["entity_id"] for entity in context["visible_entities"]}
    assert {"mira_craftswoman", "target_barrel", "stone_flat_1"} <= visible_ids


def test_ollama_parser_uses_structured_schema_and_returns_canonical_action() -> None:
    captured: dict[str, object] = {}

    def fake_transport(url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        captured["url"] = url
        captured["payload"] = payload
        captured["timeout"] = timeout
        content = {
            "recognized": True,
            "action_type": "THROW",
            "target_id": "target_barrel",
            "item_id": "stone_flat_1",
            "destination_id": None,
            "aimed": True,
            "ticks": 1,
        }
        return {"message": {"content": json.dumps(content)}}

    parser = OllamaActionParser(model="local-test", transport=fake_transport)
    action = parser.parse(
        "Прицелюсь получше и запущу плоский камень в старую бочку",
        {
            "location_id": "workshop_yard",
            "exits": ["village_square"],
            "inventory": ["stone_flat_1"],
            "visible_entities": [
                {"entity_id": "target_barrel", "entity_type": "object", "name": "Старая бочка"}
            ],
        },
    )

    assert action is not None
    assert action.action_type == ActionType.THROW
    assert action.item_id == "stone_flat_1"
    assert action.target_id == "target_barrel"
    assert action.modifiers == {"aimed": True}
    assert captured["url"] == "http://localhost:11434/api/chat"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "local-test"
    assert payload["stream"] is False
    assert payload["options"] == {"temperature": 0}
    assert isinstance(payload["format"], dict)
    assert payload["format"]["type"] == "object"


def test_ollama_parser_rejects_noncanonical_action_type() -> None:
    def fake_transport(_url: str, _payload: dict[str, object], _timeout: float) -> dict[str, object]:
        content = {
            "recognized": True,
            "action_type": "CREATE_NUKE",
            "target_id": None,
            "item_id": None,
            "destination_id": None,
            "aimed": False,
            "ticks": 1,
        }
        return {"message": {"content": json.dumps(content)}}

    parser = OllamaActionParser(model="local-test", transport=fake_transport)

    assert parser.parse("создам ядерную бомбу", {}) is None
