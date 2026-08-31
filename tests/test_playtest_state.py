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


PLAYTEST_TIME = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def _client(path: Path) -> tuple[GameDatabase, TestClient, str]:
    db = GameDatabase(path)
    db.initialize()
    clock = FakeClock(PLAYTEST_TIME)
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest)
    client = TestClient(create_app(game, quest, dialogue))
    player_id = client.post(
        "/api/session",
        json={"external_id": "playtest-player", "name": "Playtester"},
    ).json()["player_id"]
    return db, client, player_id


def _action(client: TestClient, player_id: str, external_id: str, action_type: str, **payload):
    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": action_type,
            "external_id": external_id,
            **payload,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True, body
    return body


def test_state_exposes_living_world_without_internal_goal_ids(tmp_path: Path) -> None:
    _, client, player_id = _client(tmp_path / "world.sqlite3")

    initial = client.get(f"/api/state/{player_id}").json()["living_world"]
    assert initial == {
        "tick": 0,
        "mira": {
            "location_id": "workshop_yard",
            "status": "working",
            "wood_stock": 2,
        },
        "kaspar": {
            "location_id": "village_square",
            "status": "schedule",
            "carrying_wood": False,
        },
        "recent_events": [],
    }

    _action(
        client,
        player_id,
        "wait-for-request",
        "WAIT",
        modifiers={"ticks": 5},
    )
    requested = client.get(f"/api/state/{player_id}").json()["living_world"]

    assert requested["tick"] == 5
    assert requested["mira"] == {
        "location_id": "workshop_yard",
        "status": "needs_wood",
        "wood_stock": 0,
    }
    assert requested["kaspar"] == {
        "location_id": "river_edge",
        "status": "collecting_wood",
        "carrying_wood": False,
    }
    assert "goal" not in requested["kaspar"]
    assert [event["event_type"] for event in requested["recent_events"]][-2:] == [
        "NPC_REQUESTED_RESOURCE",
        "NPC_MOVED",
    ]


def test_state_reflects_player_intervention_and_schedule_restore(tmp_path: Path) -> None:
    _, client, player_id = _client(tmp_path / "world.sqlite3")

    _action(client, player_id, "wait-five", "WAIT", modifiers={"ticks": 5})
    _action(client, player_id, "to-square", "MOVE", destination_id="village_square")
    _action(client, player_id, "to-river", "MOVE", destination_id="river_edge")
    _action(client, player_id, "take-driftwood", "TAKE", target_id="driftwood_1")
    _action(client, player_id, "kaspar-blocked", "WAIT", modifiers={"ticks": 1})

    blocked_state = client.get(f"/api/state/{player_id}").json()
    assert "driftwood_1" in {item["entity_id"] for item in blocked_state["inventory"]}
    assert blocked_state["living_world"]["kaspar"] == {
        "location_id": "river_edge",
        "status": "collecting_wood",
        "carrying_wood": False,
    }

    _action(client, player_id, "return-square", "MOVE", destination_id="village_square")
    _action(client, player_id, "return-workshop", "MOVE", destination_id="workshop_yard")
    _action(
        client,
        player_id,
        "give-driftwood",
        "GIVE",
        target_id="driftwood_1",
        recipient_id="npc_mira",
    )

    satisfied = client.get(f"/api/state/{player_id}").json()
    assert "driftwood_1" not in {item["entity_id"] for item in satisfied["inventory"]}
    assert satisfied["living_world"]["mira"] == {
        "location_id": "workshop_yard",
        "status": "working",
        "wood_stock": 1,
    }
    assert satisfied["living_world"]["kaspar"] == {
        "location_id": "village_square",
        "status": "schedule",
        "carrying_wood": False,
    }
    assert "NPC_DELIVERED_RESOURCE" not in {
        event["event_type"] for event in satisfied["living_world"]["recent_events"]
    }
