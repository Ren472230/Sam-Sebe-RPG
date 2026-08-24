from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from samseberpg.db import GameDatabase
from samseberpg.server import build_app


class FailingProvider:
    def generate(self, context):
        raise RuntimeError("LLM intentionally unavailable")


def action(client: TestClient, player_id: str, *, kind: str, target: str | None = None, destination: str | None = None, external_id: str):
    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": kind,
            "target_id": target,
            "destination_id": destination,
            "external_id": external_id,
        },
    )
    assert response.status_code == 200
    return response.json()


def move(client: TestClient, player_id: str, destination: str, step: str) -> None:
    result = action(
        client,
        player_id,
        kind="MOVE",
        destination=destination,
        external_id=f"acceptance-move-{step}",
    )
    assert result["success"] is True


def test_full_vertical_slice_survives_restart_without_llm(tmp_path: Path) -> None:
    db_path = tmp_path / "world.sqlite3"
    client = TestClient(build_app(db_path, provider=FailingProvider()))
    player_id = client.post("/api/session", json={"name": "Ren"}).json()["player_id"]

    move(client, player_id, "village_square", "01-square")
    move(client, player_id, "tavern_interior", "02-tavern")
    dialogue = client.post(
        "/api/dialogue", json={"player_id": player_id, "user_text": "Есть работа?"}
    ).json()
    assert dialogue["used_fallback"] is True
    assert dialogue["proposal"] == "offer_quest:bring_5_firewood"
    accepted = client.post(
        "/api/quest/accept",
        json={"player_id": player_id, "external_id": "acceptance-accept"},
    ).json()
    assert accepted["success"] is True

    move(client, player_id, "village_square", "03-outside")
    move(client, player_id, "workshop_yard", "04-workshop")
    for index in range(1, 5):
        result = action(
            client,
            player_id,
            kind="TAKE",
            target=f"firewood_{index}",
            external_id=f"acceptance-take-{index}",
        )
        assert result["success"] is True

    move(client, player_id, "village_square", "05-square")
    move(client, player_id, "tavern_interior", "06-tavern")
    early = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-early-turn-in"},
    ).json()
    assert early["success"] is False
    assert early["code"] == "INSUFFICIENT_FIREWOOD"
    assert early["state"]["owned_firewood"] == 4

    move(client, player_id, "village_square", "07-outside")
    move(client, player_id, "workshop_yard", "08-workshop")
    fifth = action(
        client,
        player_id,
        kind="TAKE",
        target="firewood_5",
        external_id="acceptance-take-5",
    )
    assert fifth["success"] is True
    move(client, player_id, "village_square", "09-square")
    move(client, player_id, "tavern_interior", "10-tavern")
    complete = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-final-turn-in"},
    ).json()
    assert complete["success"] is True
    assert complete["state"]["status"] == "completed"

    duplicate = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-duplicate-turn-in"},
    ).json()
    assert duplicate["code"] == "ALREADY_COMPLETED"

    before_restart = client.get(f"/api/state/{player_id}").json()
    assert before_restart["quest"]["status"] == "completed"
    assert before_restart["coins"] == 15
    assert before_restart["oren_trust"] == 10

    restarted = TestClient(build_app(db_path, provider=FailingProvider()))
    same_player = restarted.post("/api/session", json={"name": "Ren"}).json()["player_id"]
    assert same_player == player_id
    after_restart = restarted.get(f"/api/state/{player_id}").json()
    assert after_restart["quest"]["status"] == "completed"
    assert after_restart["coins"] == 15
    assert after_restart["oren_trust"] == 10

    acknowledgement = restarted.post(
        "/api/dialogue", json={"player_id": player_id, "user_text": "Ты меня помнишь?"}
    ).json()
    assert acknowledgement["used_fallback"] is True
    assert "помню" in acknowledgement["text"].lower()

    db = GameDatabase(db_path)
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_memories WHERE npc_actor_id = 'npc_oren' AND subject_actor_id = ?",
            (player_id,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE action_type = 'QUEST_TURN_IN' AND success = 1"
        ).fetchone()[0] == 1
