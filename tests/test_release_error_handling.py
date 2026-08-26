from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.game import GameService
from samseberpg.quest import QuestService


class FailingProvider:
    def generate(self, context):
        raise RuntimeError("offline")


def test_http_rejects_invalid_action_and_impossible_move_without_mutating_state(tmp_path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=FailingProvider())
    client = TestClient(create_app(game, quest, dialogue))

    session = client.post("/api/session", json={"external_id": "error-gate", "name": "Ren"})
    assert session.status_code == 200
    player_id = session.json()["player_id"]

    invalid_action = client.post(
        "/api/action",
        json={"player_id": player_id, "action_type": "DANCE", "external_id": "invalid-action"},
    )
    assert invalid_action.status_code == 422

    impossible_move = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "MOVE",
            "destination_id": "missing_location",
            "external_id": "impossible-move",
        },
    )
    assert impossible_move.status_code == 200
    payload = impossible_move.json()
    assert payload["success"] is False
    assert payload["code"] == "INVALID_DESTINATION"

    state = client.get(f"/api/state/{player_id}")
    assert state.status_code == 200
    assert state.json()["location"]["id"] == "workshop_yard"
