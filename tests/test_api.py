from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

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


def make_client(tmp_path: Path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=FailingProvider())
    return db, TestClient(create_app(game, quest, dialogue))


def create_player(client: TestClient) -> str:
    response = client.post("/api/session", json={"name": "Ren"})
    assert response.status_code == 200
    return response.json()["player_id"]


def test_health_session_and_state_projection_are_stable(tmp_path: Path) -> None:
    _, client = make_client(tmp_path)

    assert client.get("/api/health").json() == {"ok": True}
    player = create_player(client)
    same_player = create_player(client)
    assert same_player == player

    state = client.get(f"/api/state/{player}")
    assert state.status_code == 200
    payload = state.json()
    assert payload["world"]["location_id"] == "workshop_yard"
    assert payload["quest"]["status"] == "available"
    assert payload["quest"]["owned_firewood"] == 0
    assert payload["coins"] == 10
    assert payload["oren_trust"] == 0


def test_move_to_tavern_uses_authoritative_actions_and_exposes_oren(tmp_path: Path) -> None:
    _, client = make_client(tmp_path)
    player = create_player(client)

    move_square = client.post(
        "/api/action",
        json={
            "player_id": player,
            "action_type": "MOVE",
            "destination_id": "village_square",
            "external_id": "move-square",
        },
    )
    move_tavern = client.post(
        "/api/action",
        json={
            "player_id": player,
            "action_type": "MOVE",
            "destination_id": "tavern_interior",
            "external_id": "move-tavern",
        },
    )

    assert move_square.json()["success"] is True
    assert move_tavern.json()["success"] is True
    state = client.get(f"/api/state/{player}").json()
    assert state["world"]["location_id"] == "tavern_interior"
    assert "npc_oren" in {actor["actor_id"] for actor in state["world"]["visible_actors"]}


def test_api_completes_firewood_route_with_dialogue_fallback(tmp_path: Path) -> None:
    db, client = make_client(tmp_path)
    player = create_player(client)

    dialogue = client.post(
        "/api/dialogue", json={"player_id": player, "user_text": "Есть работа?"}
    )
    assert dialogue.status_code == 200
    assert dialogue.json()["used_fallback"] is True
    assert dialogue.json()["proposal"] == "offer_quest:bring_5_firewood"

    accepted = client.post(
        "/api/quest/accept",
        json={"player_id": player, "external_id": "accept-api"},
    )
    assert accepted.json()["success"] is True

    for index in range(1, 6):
        take = client.post(
            "/api/action",
            json={
                "player_id": player,
                "action_type": "TAKE",
                "target_id": f"firewood_{index}",
                "external_id": f"take-{index}",
            },
        )
        assert take.json()["success"] is True

    turn_in = client.post(
        "/api/quest/turn-in",
        json={"player_id": player, "external_id": "turn-in-api"},
    )
    replay = client.post(
        "/api/quest/turn-in",
        json={"player_id": player, "external_id": "turn-in-api-2"},
    )

    assert turn_in.json()["success"] is True
    assert replay.json()["code"] == "ALREADY_COMPLETED"
    state = client.get(f"/api/state/{player}").json()
    assert state["quest"]["status"] == "completed"
    assert state["coins"] == 15
    assert state["oren_trust"] == 10
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM npc_memories").fetchone()[0] == 1


def test_server_module_exists() -> None:
    import importlib.util
    assert importlib.util.find_spec("samseberpg.server") is not None


def test_server_build_app_works_without_openai_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from samseberpg.server import build_app

    app = build_app(tmp_path / "server-world.sqlite3")
    client = TestClient(app)

    assert client.get("/api/health").json() == {"ok": True}
    dialogue = client.post("/api/session", json={"name": "Ren"})
    assert dialogue.status_code == 200
