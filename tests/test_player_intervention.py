from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from samseberpg.api import ActionRequest, create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService

EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def test_give_action_contract_exposes_recipient() -> None:
    action = CanonicalAction(
        actor_id="player_1",
        action_type=ActionType.GIVE,
        target_id="driftwood_1",
        recipient_id="npc_mira",
    )

    assert action.action_type.value == "GIVE"
    assert action.target_id == "driftwood_1"
    assert action.recipient_id == "npc_mira"


def test_action_request_preserves_give_recipient() -> None:
    request = ActionRequest(
        player_id="player_1",
        action_type=ActionType.GIVE,
        target_id="driftwood_1",
        recipient_id="npc_mira",
    )

    assert request.recipient_id == "npc_mira"


def test_player_can_take_kaspars_resource_and_satisfy_mira(tmp_path: Path) -> None:
    db, game, player_id = _services(tmp_path / "player-intervention.sqlite3")

    _wait_for_request(game, db, player_id, "wait-for-request")
    _take_driftwood(game, player_id, "race")

    blocked = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 1},
        ),
        external_id="kaspar-blocked",
    )
    assert blocked.success is True
    assert _runtime(db, "npc_kaspar")[:2] == (
        1,
        {"carrying_wood": 0, "goal": "collect_wood"},
    )
    with db.connect() as conn:
        collected_count = int(conn.execute(
            "SELECT COUNT(*) FROM world_events WHERE event_type='NPC_COLLECTED_RESOURCE'"
        ).fetchone()[0])
        item = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id='driftwood_1'"
        ).fetchone()
    assert collected_count == 0
    assert item is not None and item[0] is None and item[1] == player_id

    _return_to_mira(game, player_id, "race")
    given = _give(game, player_id, "give-driftwood")

    assert given.success is True
    assert given.code == "OK"
    assert _runtime(db, "npc_mira")[:2] == (
        0,
        {"wood_stock": 1, "work_cycles": 2, "requested_wood": False},
    )
    assert _runtime(db, "npc_kaspar")[:2] == (
        0,
        {"carrying_wood": 0, "goal": None},
    )

    with db.connect() as conn:
        item = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id='driftwood_1'"
        ).fetchone()
        locations = {
            str(row[0]): str(row[1])
            for row in conn.execute(
                "SELECT id, location_id FROM actors WHERE id IN ('npc_mira','npc_kaspar')"
            ).fetchall()
        }
        give_events = conn.execute(
            "SELECT action_type,target_id,evidence_json FROM action_events "
            "WHERE external_id='give-driftwood'"
        ).fetchall()
        delivered_count = int(conn.execute(
            "SELECT COUNT(*) FROM world_events WHERE event_type='NPC_DELIVERED_RESOURCE'"
        ).fetchone()[0])

    assert item is not None and item[0] is None and item[1] is None
    assert locations == {"npc_mira": "workshop_yard", "npc_kaspar": "village_square"}
    assert len(give_events) == 1
    assert tuple(give_events[0][:2]) == ("GIVE", "driftwood_1")
    assert json.loads(str(give_events[0][2]))["recipient_id"] == "npc_mira"
    assert delivered_count == 0


def test_give_before_mira_requests_wood_does_not_mutate_world(tmp_path: Path) -> None:
    db, game, player_id = _services(tmp_path / "no-request.sqlite3")
    _take_driftwood(game, player_id, "no-request")
    _return_to_mira(game, player_id, "no-request")
    before_mira = _runtime(db, "npc_mira")
    before_kaspar = _runtime(db, "npc_kaspar")

    result = _give(game, player_id, "give-too-early")

    assert result.success is False
    assert result.code == "RESOURCE_NOT_NEEDED"
    assert _item_owner(db, "driftwood_1") == player_id
    assert _runtime(db, "npc_mira") == before_mira
    assert _runtime(db, "npc_kaspar") == before_kaspar


def test_wrong_resource_does_not_satisfy_mira(tmp_path: Path) -> None:
    db, game, player_id = _services(tmp_path / "wrong-resource.sqlite3")
    _wait_for_request(game, db, player_id, "wait-wrong-resource")
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="wood_block_1",
        ),
        external_id="take-wrong-resource",
    )
    assert taken.success is True
    before_mira = _runtime(db, "npc_mira")
    before_kaspar = _runtime(db, "npc_kaspar")

    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="wood_block_1",
            recipient_id="npc_mira",
        ),
        external_id="give-wrong-resource",
    )

    assert result.success is False
    assert result.code == "UNSUPPORTED_RESOURCE"
    assert _item_owner(db, "wood_block_1") == player_id
    assert _runtime(db, "npc_mira") == before_mira
    assert _runtime(db, "npc_kaspar") == before_kaspar


def test_give_requires_recipient_to_be_present(tmp_path: Path) -> None:
    db, game, player_id = _services(tmp_path / "recipient-distance.sqlite3")
    _wait_for_request(game, db, player_id, "wait-distance")
    _take_driftwood(game, player_id, "distance")
    before_mira = _runtime(db, "npc_mira")
    before_kaspar = _runtime(db, "npc_kaspar")

    result = _give(game, player_id, "give-from-river")

    assert result.success is False
    assert result.code == "RECIPIENT_NOT_PRESENT"
    assert _item_owner(db, "driftwood_1") == player_id
    assert _runtime(db, "npc_mira") == before_mira
    assert _runtime(db, "npc_kaspar") == before_kaspar


def test_give_to_wrong_npc_does_not_mutate_request(tmp_path: Path) -> None:
    db, game, player_id = _services(tmp_path / "wrong-recipient.sqlite3")
    _wait_for_request(game, db, player_id, "wait-wrong-recipient")
    _take_driftwood(game, player_id, "wrong-recipient")
    before_mira = _runtime(db, "npc_mira")
    before_kaspar = _runtime(db, "npc_kaspar")

    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="driftwood_1",
            recipient_id="npc_kaspar",
        ),
        external_id="give-to-kaspar",
    )

    assert result.success is False
    assert result.code == "UNSUPPORTED_RECIPIENT"
    assert _item_owner(db, "driftwood_1") == player_id
    assert _runtime(db, "npc_mira") == before_mira
    assert _runtime(db, "npc_kaspar") == before_kaspar


def test_successful_give_is_idempotent_by_external_id(tmp_path: Path) -> None:
    db, game, player_id = _services(tmp_path / "give-idempotent.sqlite3")
    _wait_for_request(game, db, player_id, "wait-idempotent")
    _take_driftwood(game, player_id, "idempotent")
    _return_to_mira(game, player_id, "idempotent")
    action = CanonicalAction(
        actor_id=player_id,
        action_type=ActionType.GIVE,
        target_id="driftwood_1",
        recipient_id="npc_mira",
    )

    first = game.execute(action, external_id="give-once")
    second = game.execute(action, external_id="give-once")

    assert first.success is True
    assert second.success is True
    assert second.replayed is True
    assert second.event_id == first.event_id
    assert _runtime(db, "npc_mira")[1]["wood_stock"] == 1
    with db.connect() as conn:
        give_count = int(conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE external_id='give-once'"
        ).fetchone()[0])
    assert give_count == 1


def test_action_api_executes_successful_give(tmp_path: Path) -> None:
    path = tmp_path / "give-api.sqlite3"
    db = GameDatabase(path)
    db.initialize()
    clock = FakeClock(EVENING)
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest)
    client = TestClient(create_app(game, quest, dialogue))
    player_id = game.register_player("give-api", "Player")

    _wait_for_request(game, db, player_id, "api-wait")
    _take_driftwood(game, player_id, "api")
    _return_to_mira(game, player_id, "api")

    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "GIVE",
            "target_id": "driftwood_1",
            "recipient_id": "npc_mira",
            "external_id": "api-give",
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert response.json()["code"] == "OK"
    assert _runtime(db, "npc_mira")[:2] == (
        0,
        {"wood_stock": 1, "work_cycles": 2, "requested_wood": False},
    )


def _services(path: Path) -> tuple[GameDatabase, GameService, str]:
    db = GameDatabase(path)
    db.initialize()
    game = GameService(db, FakeClock(EVENING), living_world=LivingWorldService())
    player_id = game.register_player(path.stem, "Player")
    return db, game, player_id


def _wait_for_request(
    game: GameService,
    db: GameDatabase,
    player_id: str,
    external_id: str,
) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 5},
        ),
        external_id=external_id,
    )
    assert result.success is True
    assert _runtime(db, "npc_mira")[:2] == (
        1,
        {"wood_stock": 0, "work_cycles": 2, "requested_wood": True},
    )
    assert _runtime(db, "npc_kaspar")[:2] == (
        1,
        {"carrying_wood": 0, "goal": "collect_wood"},
    )


def _take_driftwood(game: GameService, player_id: str, prefix: str) -> None:
    _move(game, player_id, "village_square", f"{prefix}-to-square")
    _move(game, player_id, "river_edge", f"{prefix}-to-river")
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="driftwood_1",
        ),
        external_id=f"{prefix}-take-driftwood",
    )
    assert result.success is True


def _return_to_mira(game: GameService, player_id: str, prefix: str) -> None:
    _move(game, player_id, "village_square", f"{prefix}-return-square")
    _move(game, player_id, "workshop_yard", f"{prefix}-return-workshop")


def _give(game: GameService, player_id: str, external_id: str):
    return game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="driftwood_1",
            recipient_id="npc_mira",
        ),
        external_id=external_id,
    )


def _move(game: GameService, player_id: str, destination: str, external_id: str) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.MOVE,
            destination_id=destination,
        ),
        external_id=external_id,
    )
    assert result.success is True


def _item_owner(db: GameDatabase, entity_id: str) -> str | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id=?",
            (entity_id,),
        ).fetchone()
    assert row is not None
    return None if row[0] is None else str(row[0])


def _runtime(db: GameDatabase, npc_id: str) -> tuple[int, dict[str, object], int]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT override_active,state_json,updated_tick FROM npc_runtime_state "
            "WHERE npc_actor_id=?",
            (npc_id,),
        ).fetchone()
    assert row is not None
    return int(row[0]), json.loads(str(row[1])), int(row[2])
