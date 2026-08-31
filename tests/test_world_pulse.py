from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService


def test_state_exposes_world_pulse_after_wait(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world-pulse.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest)
    client = TestClient(create_app(game, quest, dialogue))

    player_id = client.post(
        "/api/session",
        json={"external_id": "world-pulse-player", "name": "Player"},
    ).json()["player_id"]

    initial = client.get(f"/api/state/{player_id}").json()
    assert initial["world_pulse"] == {"tick": 0, "latest_events": []}

    waited = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "WAIT",
            "modifiers": {"ticks": 5},
            "external_id": "world-pulse-wait-five",
        },
    ).json()
    assert waited["success"] is True

    pulse = client.get(f"/api/state/{player_id}").json()["world_pulse"]
    assert pulse["tick"] == 5
    assert len(pulse["latest_events"]) >= 2
    event_types = {event["event_type"] for event in pulse["latest_events"]}
    assert "NPC_REQUESTED_RESOURCE" in event_types
    assert "NPC_COLLECTED_RESOURCE" in event_types
    for event in pulse["latest_events"]:
        assert set(event) == {"tick", "actor_id", "event_type", "summary"}
