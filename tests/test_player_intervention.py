from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.api import ActionRequest
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService

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
    db = GameDatabase(tmp_path / "player-intervention.sqlite3")
    db.initialize()
    game = GameService(db, FakeClock(EVENING), living_world=LivingWorldService())
    player_id = game.register_player("player-intervention", "Player")

    assert game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 5},
        ),
        external_id="wait-for-request",
    ).success
    assert _runtime(db, "npc_mira")[:2] == (
        1,
        {"wood_stock": 0, "work_cycles": 2, "requested_wood": True},
    )
    assert _runtime(db, "npc_kaspar")[:2] == (
        1,
        {"carrying_wood": 0, "goal": "collect_wood"},
    )

    _move(game, player_id, "village_square", "move-to-square")
    _move(game, player_id, "river_edge", "move-to-river")
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="driftwood_1",
        ),
        external_id="take-driftwood",
    )
    assert taken.success is True

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

    _move(game, player_id, "village_square", "return-to-square")
    _move(game, player_id, "workshop_yard", "return-to-workshop")
    given = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="driftwood_1",
            recipient_id="npc_mira",
        ),
        external_id="give-driftwood",
    )

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


def _runtime(db: GameDatabase, npc_id: str) -> tuple[int, dict[str, object], int]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT override_active,state_json,updated_tick FROM npc_runtime_state "
            "WHERE npc_actor_id=?",
            (npc_id,),
        ).fetchone()
    assert row is not None
    return int(row[0]), json.loads(str(row[1])), int(row[2])
