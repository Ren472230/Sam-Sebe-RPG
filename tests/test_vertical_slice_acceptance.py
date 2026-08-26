from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from samseberpg.db import GameDatabase
from samseberpg.server import build_app


QUEST_TYPE = "bring_5_firewood"
QUEST_OFFER = f"offer_quest:{QUEST_TYPE}"
EXPECTED_COIN_REWARD = 5
EXPECTED_TRUST_REWARD = 10


class DeterministicProvider:
    """Network-free provider that reflects only the supplied canonical context."""

    def generate(self, context):
        state = context.quest
        if state.status == "available":
            return SimpleNamespace(text="Принеси пять поленьев.", proposal=QUEST_OFFER)
        if state.status == "active" and state.owned_firewood < state.required_firewood:
            return SimpleNamespace(
                text=f"Пока {state.owned_firewood} из {state.required_firewood}.",
                proposal=None,
            )
        if state.status == "active":
            return SimpleNamespace(text="Все пять на месте.", proposal=None)
        memory_text = " ".join(context.memories).lower()
        text = "Помню, ты помог с дровами." if "firewood" in memory_text else "Спасибо за помощь."
        return SimpleNamespace(text=text, proposal=None)


class FailingProvider:
    def generate(self, context):
        raise RuntimeError("LLM intentionally unavailable")


def _session(client: TestClient, *, name: str = "Player") -> str:
    response = client.post(
        "/api/session",
        json={"external_id": "local-player", "name": name},
    )
    assert response.status_code == 200, response.text
    player_id = response.json().get("player_id")
    assert isinstance(player_id, str) and player_id
    return player_id


def _state(client: TestClient, player_id: str) -> dict:
    response = client.get(f"/api/state/{player_id}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert isinstance(payload.get("quest"), dict)
    assert "coins" in payload
    _world(payload)
    _trust(payload)
    return payload


def _world(state: dict) -> dict:
    world = state.get("world", state)
    for key in ("location_id", "visible_actors", "visible_entities", "inventory"):
        assert key in world, f"state is missing world field {key!r}: {state}"
    return world


def _trust(state: dict) -> int:
    if "oren_trust" in state:
        return int(state["oren_trust"])
    relation = state.get("oren_relation")
    if isinstance(relation, dict) and "trust" in relation:
        return int(relation["trust"])
    relations = state.get("relations")
    if isinstance(relations, dict):
        oren = relations.get("npc_oren")
        if isinstance(oren, dict) and "trust" in oren:
            return int(oren["trust"])
    raise AssertionError(f"state is missing Oren trust/relation: {state}")


def _firewood_inventory_count(state: dict) -> int:
    count = 0
    for item in _world(state)["inventory"]:
        if isinstance(item, str):
            entity_id = item
            entity_type = ""
        else:
            entity_id = str(item.get("entity_id", item.get("id", "")))
            entity_type = str(item.get("entity_type", item.get("type", "")))
        if entity_type == "firewood" or entity_id.startswith("firewood_"):
            count += 1
    return count


def _action(
    client: TestClient,
    player_id: str,
    *,
    action_type: str,
    external_id: str,
    target_id: str | None = None,
    destination_id: str | None = None,
) -> dict:
    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": action_type,
            "target_id": target_id,
            "destination_id": destination_id,
            "external_id": external_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _move(client: TestClient, player_id: str, destination_id: str, step: str) -> None:
    result = _action(
        client,
        player_id,
        action_type="MOVE",
        destination_id=destination_id,
        external_id=f"acceptance-move-{step}",
    )
    assert result["success"] is True, result


def _memory_count(db_path: Path, player_id: str) -> int:
    db = GameDatabase(db_path)
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_memories "
                "WHERE npc_actor_id = 'npc_oren' AND subject_actor_id = ?",
                (player_id,),
            ).fetchone()[0]
        )


def _successful_turn_in_count(db_path: Path, player_id: str) -> int:
    db = GameDatabase(db_path)
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM action_events "
                "WHERE actor_id = ? AND action_type = 'QUEST_TURN_IN' AND success = 1",
                (player_id,),
            ).fetchone()[0]
        )


def _run_complete_route(
    db_path: Path,
    *,
    provider,
    expect_fallback: bool,
) -> tuple[str, dict]:
    client = TestClient(build_app(db_path, provider=provider))
    player_id = _session(client)
    start = _state(client, player_id)
    assert _world(start)["location_id"] == "workshop_yard"
    assert start["quest"]["status"] == "available"
    initial_coins = int(start["coins"])
    initial_trust = _trust(start)
    initial_memories = _memory_count(db_path, player_id)

    looked = _action(
        client,
        player_id,
        action_type="LOOK",
        external_id="acceptance-look-start",
    )
    assert looked["success"] is True, looked

    _move(client, player_id, "village_square", "01-square")
    _move(client, player_id, "tavern_interior", "02-tavern")
    offer = client.post(
        "/api/dialogue",
        json={"player_id": player_id, "user_text": "Есть работа?"},
    )
    assert offer.status_code == 200, offer.text
    offer_payload = offer.json()
    assert offer_payload["proposal"] == QUEST_OFFER
    assert bool(offer_payload["used_fallback"]) is expect_fallback

    accepted = client.post(
        "/api/quest/accept",
        json={"player_id": player_id, "external_id": "acceptance-accept"},
    )
    assert accepted.status_code == 200, accepted.text
    accepted_payload = accepted.json()
    assert accepted_payload["success"] is True, accepted_payload
    assert accepted_payload["state"]["status"] == "active"

    _move(client, player_id, "village_square", "03-outside")
    _move(client, player_id, "workshop_yard", "04-workshop")
    for index in range(1, 5):
        taken = _action(
            client,
            player_id,
            action_type="TAKE",
            target_id=f"firewood_{index}",
            external_id=f"acceptance-take-{index}",
        )
        assert taken["success"] is True, taken
        current = _state(client, player_id)
        assert current["quest"]["owned_firewood"] == index
        assert _firewood_inventory_count(current) == index

    _move(client, player_id, "village_square", "05-square")
    _move(client, player_id, "tavern_interior", "06-tavern")
    early = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-early-turn-in"},
    )
    assert early.status_code == 200, early.text
    early_payload = early.json()
    assert early_payload["success"] is False
    assert early_payload["code"] == "INSUFFICIENT_FIREWOOD"
    assert early_payload["state"]["owned_firewood"] == 4
    after_early = _state(client, player_id)
    assert int(after_early["coins"]) == initial_coins
    assert _trust(after_early) == initial_trust
    assert _memory_count(db_path, player_id) == initial_memories

    _move(client, player_id, "village_square", "07-outside")
    _move(client, player_id, "workshop_yard", "08-workshop")
    fifth = _action(
        client,
        player_id,
        action_type="TAKE",
        target_id="firewood_5",
        external_id="acceptance-take-5",
    )
    assert fifth["success"] is True, fifth
    ready = _state(client, player_id)
    assert ready["quest"]["owned_firewood"] == 5
    assert _firewood_inventory_count(ready) == 5

    _move(client, player_id, "village_square", "09-square")
    _move(client, player_id, "tavern_interior", "10-tavern")
    complete = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-final-turn-in"},
    )
    assert complete.status_code == 200, complete.text
    complete_payload = complete.json()
    assert complete_payload["success"] is True, complete_payload
    assert complete_payload["state"]["status"] == "completed"

    completed_state = _state(client, player_id)
    assert completed_state["quest"]["status"] == "completed"
    assert completed_state["quest"]["owned_firewood"] == 0
    assert _firewood_inventory_count(completed_state) == 0
    assert int(completed_state["coins"]) == initial_coins + EXPECTED_COIN_REWARD
    assert _trust(completed_state) == initial_trust + EXPECTED_TRUST_REWARD
    assert _memory_count(db_path, player_id) == initial_memories + 1
    assert _successful_turn_in_count(db_path, player_id) == 1

    replay = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-final-turn-in"},
    )
    assert replay.status_code == 200, replay.text
    replay_payload = replay.json()
    assert replay_payload["success"] is True
    assert replay_payload.get("replayed") is True

    duplicate = client.post(
        "/api/quest/turn-in",
        json={"player_id": player_id, "external_id": "acceptance-duplicate-turn-in"},
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_payload = duplicate.json()
    assert duplicate_payload["success"] is False
    assert duplicate_payload["code"] == "ALREADY_COMPLETED"

    after_duplicate = _state(client, player_id)
    assert int(after_duplicate["coins"]) == int(completed_state["coins"])
    assert _trust(after_duplicate) == _trust(completed_state)
    assert _memory_count(db_path, player_id) == initial_memories + 1
    assert _successful_turn_in_count(db_path, player_id) == 1

    consequence = client.post(
        "/api/dialogue",
        json={"player_id": player_id, "user_text": "Ты меня помнишь?"},
    )
    assert consequence.status_code == 200, consequence.text
    consequence_payload = consequence.json()
    assert bool(consequence_payload["used_fallback"]) is expect_fallback
    assert consequence_payload["text"] != offer_payload["text"]
    assert "пом" in consequence_payload["text"].lower()

    restarted = TestClient(build_app(db_path, provider=provider))
    same_player = _session(restarted, name="Player after restart")
    assert same_player == player_id
    restored = _state(restarted, player_id)
    assert _world(restored)["location_id"] == "tavern_interior"
    assert restored["quest"]["status"] == "completed"
    assert int(restored["coins"]) == initial_coins + EXPECTED_COIN_REWARD
    assert _trust(restored) == initial_trust + EXPECTED_TRUST_REWARD
    assert _memory_count(db_path, player_id) == initial_memories + 1
    assert _successful_turn_in_count(db_path, player_id) == 1

    restored_dialogue = restarted.post(
        "/api/dialogue",
        json={"player_id": player_id, "user_text": "Что изменилось?"},
    )
    assert restored_dialogue.status_code == 200, restored_dialogue.text
    restored_payload = restored_dialogue.json()
    assert bool(restored_payload["used_fallback"]) is expect_fallback
    assert "пом" in restored_payload["text"].lower()
    return player_id, restored


def test_vertical_slice_full_loop_and_restart_without_real_openai(tmp_path: Path) -> None:
    _run_complete_route(
        tmp_path / "world.sqlite3",
        provider=DeterministicProvider(),
        expect_fallback=False,
    )


def test_vertical_slice_remains_completable_with_openai_unavailable(tmp_path: Path) -> None:
    _run_complete_route(
        tmp_path / "fallback.sqlite3",
        provider=FailingProvider(),
        expect_fallback=True,
    )


def test_frozen_api_contract_supports_health_session_state_look_take_and_drop(tmp_path: Path) -> None:
    db_path = tmp_path / "contract.sqlite3"
    client = TestClient(build_app(db_path, provider=FailingProvider()))

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {"ok": True}

    player_id = _session(client)
    assert _session(client, name="Renamed but same local player") == player_id
    state = _state(client, player_id)
    assert _world(state)["location_id"] == "workshop_yard"

    looked = _action(
        client,
        player_id,
        action_type="LOOK",
        external_id="acceptance-contract-look",
    )
    assert looked["success"] is True

    taken = _action(
        client,
        player_id,
        action_type="TAKE",
        target_id="stone_flat_1",
        external_id="acceptance-contract-take",
    )
    assert taken["success"] is True
    assert any(
        str(item.get("entity_id", item.get("id", ""))) == "stone_flat_1"
        for item in _world(_state(client, player_id))["inventory"]
        if isinstance(item, dict)
    )

    dropped = _action(
        client,
        player_id,
        action_type="DROP",
        target_id="stone_flat_1",
        external_id="acceptance-contract-drop",
    )
    assert dropped["success"] is True
    assert not any(
        str(item.get("entity_id", item.get("id", ""))) == "stone_flat_1"
        for item in _world(_state(client, player_id))["inventory"]
        if isinstance(item, dict)
    )
