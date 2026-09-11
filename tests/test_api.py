from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueDecision, DialogueService
from samseberpg.game import GameService
from samseberpg.quest import QuestService


class FailingProvider:
    def generate(self, context):
        raise RuntimeError("offline")


class EchoProvider:
    def generate(self, context):
        return DialogueDecision(text=f"heard:{context.user_text}")


def make_client(db_path: Path, *, provider=None):
    db = GameDatabase(db_path)
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=provider or FailingProvider())
    return db, TestClient(create_app(game, quest, dialogue))


def create_player(
    client: TestClient,
    *,
    external_id: str = "local-player",
    name: str = "Ren",
) -> str:
    response = client.post(
        "/api/session",
        json={"external_id": external_id, "name": name},
    )
    assert response.status_code == 200
    return response.json()["player_id"]


def move_player(
    client: TestClient,
    player_id: str,
    destination_id: str,
    external_id: str,
) -> None:
    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "MOVE",
            "destination_id": destination_id,
            "external_id": external_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


def move_to_tavern(client: TestClient, player_id: str, prefix: str) -> None:
    move_player(client, player_id, "village_square", f"{prefix}-square")
    move_player(client, player_id, "tavern_interior", f"{prefix}-tavern")


def move_to_workshop(client: TestClient, player_id: str, prefix: str) -> None:
    move_player(client, player_id, "village_square", f"{prefix}-square")
    move_player(client, player_id, "workshop_yard", f"{prefix}-workshop")


def test_health_and_session_use_frozen_external_identity_contract(tmp_path: Path) -> None:
    _, client = make_client(tmp_path / "world.sqlite3")

    assert client.get("/api/health").json() == {"ok": True}
    player = create_player(client, external_id="local-player")
    same_player = create_player(client, external_id="local-player", name="Renamed")
    other_player = create_player(client, external_id="local-player-2")

    assert same_player == player
    assert other_player != player


def test_state_matches_frozen_projection_and_exposes_oren_in_tavern(tmp_path: Path) -> None:
    _, client = make_client(tmp_path / "world.sqlite3")
    player = create_player(client)

    initial = client.get(f"/api/state/{player}")
    assert initial.status_code == 200
    payload = initial.json()
    assert payload["player_id"] == player
    assert payload["location"]["id"] == "workshop_yard"
    assert payload["location"]["name"] == "Workshop Yard"
    assert payload["location"]["description"]
    assert payload["quest"] == {
        "quest_type": "bring_5_firewood",
        "status": "available",
        "required_firewood": 5,
        "owned_firewood": 0,
    }
    assert payload["coins"] == 10
    assert payload["oren_relation"] == {
        "familiarity": 0,
        "trust": 0,
        "affinity": 0,
        "fear": 0,
        "conflict": 0,
        "romance": 0,
    }
    assert payload["living_npc"]["nearby_npc_ids"] == ["npc_mira"]

    move_to_tavern(client, player, "state")
    tavern = client.get(f"/api/state/{player}").json()
    assert tavern["location"]["id"] == "tavern_interior"
    assert "npc_oren" in {actor["actor_id"] for actor in tavern["visible_actors"]}


def test_action_response_preserves_existing_action_result_semantics(tmp_path: Path) -> None:
    _, client = make_client(tmp_path / "world.sqlite3")
    player = create_player(client)

    first = client.post(
        "/api/action",
        json={
            "player_id": player,
            "action_type": "LOOK",
            "target_id": None,
            "destination_id": None,
            "external_id": "look-once",
        },
    ).json()
    replay = client.post(
        "/api/action",
        json={
            "player_id": player,
            "action_type": "LOOK",
            "external_id": "look-once",
        },
    ).json()

    assert first["success"] is True
    assert first["code"] == "OK"
    assert first["event_id"] is not None
    assert first["replayed"] is False
    assert replay["event_id"] == first["event_id"]
    assert replay["replayed"] is True


def test_dialogue_accepts_frozen_text_field(tmp_path: Path) -> None:
    _, client = make_client(tmp_path / "world.sqlite3", provider=EchoProvider())
    player = create_player(client)
    move_to_tavern(client, player, "dialogue")

    response = client.post(
        "/api/dialogue",
        json={"player_id": player, "text": "Есть работа?"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "text": "heard:Есть работа?",
        "proposal": None,
        "used_fallback": False,
        "social_action": None,
        "npc_id": "npc_oren",
    }


def test_api_completes_exact_once_firewood_route_and_persists_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "world.sqlite3"
    db, client = make_client(db_path)
    player = create_player(client, external_id="persistent-player")

    move_to_tavern(client, player, "offer")
    offered = client.post(
        "/api/dialogue",
        json={"player_id": player, "text": "Есть работа?"},
    ).json()
    assert offered["used_fallback"] is True
    assert offered["proposal"] == "offer_quest:bring_5_firewood"

    accepted = client.post(
        "/api/quest/accept",
        json={"player_id": player, "external_id": "accept-api"},
    ).json()
    accept_replay = client.post(
        "/api/quest/accept",
        json={"player_id": player, "external_id": "accept-api"},
    ).json()
    assert accepted["success"] is True
    assert accepted["state"]["status"] == "active"
    assert accept_replay["replayed"] is True
    assert accept_replay["event_id"] == accepted["event_id"]

    move_to_workshop(client, player, "collect")
    for index in range(1, 5):
        take = client.post(
            "/api/action",
            json={
                "player_id": player,
                "action_type": "TAKE",
                "target_id": f"firewood_{index}",
                "external_id": f"take-{index}",
            },
        ).json()
        assert take["success"] is True

    early = client.post(
        "/api/quest/turn-in",
        json={"player_id": player, "external_id": "turn-in-early"},
    ).json()
    assert early["success"] is False
    assert early["code"] == "INSUFFICIENT_FIREWOOD"
    assert early["state"]["status"] == "active"
    assert early["state"]["owned_firewood"] == 4

    fifth = client.post(
        "/api/action",
        json={
            "player_id": player,
            "action_type": "TAKE",
            "target_id": "firewood_5",
            "external_id": "take-5",
        },
    ).json()
    assert fifth["success"] is True

    completed = client.post(
        "/api/quest/turn-in",
        json={"player_id": player, "external_id": "turn-in-ok"},
    ).json()
    completed_replay = client.post(
        "/api/quest/turn-in",
        json={"player_id": player, "external_id": "turn-in-ok"},
    ).json()
    duplicate = client.post(
        "/api/quest/turn-in",
        json={"player_id": player, "external_id": "turn-in-later"},
    ).json()

    assert completed["success"] is True
    assert completed["state"]["status"] == "completed"
    assert completed["state"]["owned_firewood"] == 0
    assert completed_replay["replayed"] is True
    assert completed_replay["event_id"] == completed["event_id"]
    assert duplicate["success"] is False
    assert duplicate["code"] == "ALREADY_COMPLETED"

    state = client.get(f"/api/state/{player}").json()
    assert state["coins"] == 15
    assert state["oren_relation"]["trust"] == 10
    assert state["quest"]["status"] == "completed"
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_memories WHERE npc_actor_id = 'npc_oren' AND subject_actor_id = ?",
            (player,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM entities WHERE entity_type = 'firewood' AND owner_actor_id = 'npc_oren'"
        ).fetchone()[0] == 5

    _, reopened_client = make_client(db_path)
    same_player = create_player(reopened_client, external_id="persistent-player")
    assert same_player == player
    reopened_state = reopened_client.get(f"/api/state/{player}").json()
    assert reopened_state["quest"]["status"] == "completed"
    assert reopened_state["coins"] == 15
    assert reopened_state["oren_relation"]["trust"] == 10
    move_to_tavern(reopened_client, player, "restart")
    after_restart = reopened_client.post(
        "/api/dialogue",
        json={"player_id": player, "text": "Помнишь меня?"},
    ).json()
    assert after_restart["used_fallback"] is True
    assert "помню" in after_restart["text"].lower()


def test_legacy_pr6_frontend_payloads_remain_compatible(tmp_path: Path) -> None:
    _, client = make_client(tmp_path / "world.sqlite3", provider=EchoProvider())
    session = client.post("/api/session", json={"name": "Ren"})
    assert session.status_code == 200
    player = session.json()["player_id"]

    state = client.get(f"/api/state/{player}").json()
    assert state["world"]["location_id"] == state["location"]["id"]
    assert state["oren_trust"] == state["oren_relation"]["trust"]

    move_to_tavern(client, player, "legacy")
    legacy_dialogue = client.post(
        "/api/dialogue",
        json={"player_id": player, "user_text": "legacy"},
    ).json()
    assert legacy_dialogue["text"] == "heard:legacy"
