from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.quest import QuestService


NOON = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def _services(db_path: Path, *, now: datetime = EVENING):
    db = GameDatabase(db_path)
    db.initialize()
    clock = FakeClock(now)
    game = GameService(db, clock)
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest)
    client = TestClient(create_app(game, quest, dialogue))
    return db, clock, game, client


def _player(game: GameService, external_id: str = "qa-living-world") -> str:
    return game.register_player(external_id, "QA Player")


def _api_player(client: TestClient, external_id: str = "qa-api") -> str:
    response = client.post(
        "/api/session",
        json={"external_id": external_id, "name": "QA Player"},
    )
    assert response.status_code == 200, response.text
    return str(response.json()["player_id"])


def _wait(
    game: GameService,
    player_id: str,
    ticks: int,
    external_id: str,
):
    return game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": ticks},
        ),
        external_id=external_id,
    )


def _runtime(db: GameDatabase, npc_id: str) -> tuple[int, dict, int]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT override_active, state_json, updated_tick "
            "FROM npc_runtime_state WHERE npc_actor_id = ?",
            (npc_id,),
        ).fetchone()
    assert row is not None, f"missing runtime row for {npc_id}"
    return int(row[0]), json.loads(str(row[1])), int(row[2])


def _tick(db: GameDatabase) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()
    assert row is not None
    return int(row[0])


def _actor_location(db: GameDatabase, actor_id: str) -> str | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT location_id FROM actors WHERE id = ?", (actor_id,)
        ).fetchone()
    assert row is not None
    return None if row[0] is None else str(row[0])


def _resource(db: GameDatabase):
    with db.connect() as conn:
        return conn.execute(
            "SELECT id, location_id, owner_actor_id, state_json "
            "FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()


def _events(db: GameDatabase) -> list[tuple]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT tick, actor_id, event_type, target_id, location_id, data_json "
            "FROM world_events WHERE world_id = ? ORDER BY id",
            (DEFAULT_WORLD_ID,),
        ).fetchall()
    return [
        (
            int(row[0]),
            str(row[1]),
            str(row[2]),
            None if row[3] is None else str(row[3]),
            None if row[4] is None else str(row[4]),
            json.loads(str(row[5])),
        )
        for row in rows
    ]


def _living_snapshot(db: GameDatabase) -> dict:
    with db.connect() as conn:
        runtime_rows = conn.execute(
            "SELECT npc_actor_id, override_active, state_json, updated_tick "
            "FROM npc_runtime_state ORDER BY npc_actor_id"
        ).fetchall()
        actor_rows = conn.execute(
            "SELECT actors.id, actors.location_id, npcs.current_activity "
            "FROM npcs JOIN actors ON actors.id = npcs.actor_id "
            "WHERE actors.id IN ('npc_mira', 'npc_kaspar') ORDER BY actors.id"
        ).fetchall()
        resource = conn.execute(
            "SELECT id, location_id, owner_actor_id, state_json "
            "FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()
    return {
        "tick": _tick(db),
        "runtime": [
            (str(row[0]), int(row[1]), json.loads(str(row[2])), int(row[3]))
            for row in runtime_rows
        ],
        "actors": [
            (str(row[0]), None if row[1] is None else str(row[1]), str(row[2]))
            for row in actor_rows
        ],
        "resource": None
        if resource is None
        else (
            str(resource[0]),
            None if resource[1] is None else str(resource[1]),
            None if resource[2] is None else str(resource[2]),
            json.loads(str(resource[3])),
        ),
        "events": _events(db),
    }


def _simulation_snapshot_for_invalid(db: GameDatabase) -> dict:
    with db.connect() as conn:
        actors = [
            tuple(row)
            for row in conn.execute(
                "SELECT id, location_id FROM actors ORDER BY id"
            ).fetchall()
        ]
        entities = [
            tuple(row)
            for row in conn.execute(
                "SELECT id, location_id, owner_actor_id, state_json FROM entities ORDER BY id"
            ).fetchall()
        ]
    return {
        "living": _living_snapshot(db),
        "actors": actors,
        "entities": entities,
    }


def _world_event_count(db: GameDatabase, event_type: str) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events WHERE event_type = ?", (event_type,)
            ).fetchone()[0]
        )


def test_clean_bootstrap_has_required_runtime_and_single_real_driftwood(tmp_path: Path) -> None:
    db, _, _, _ = _services(tmp_path / "bootstrap.sqlite3")

    assert _tick(db) == 0
    assert _runtime(db, "npc_mira") == (
        0,
        {"wood_stock": 2, "work_cycles": 0, "requested_wood": False},
        0,
    )
    assert _runtime(db, "npc_kaspar") == (
        0,
        {"carrying_wood": 0, "goal": None},
        0,
    )
    resource = _resource(db)
    assert resource is not None
    assert tuple(resource[:3]) == ("driftwood_1", "river_edge", None)
    assert json.loads(str(resource[3])) == {"resource_kind": "useful_wood"}

    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()[0] == 1


def test_full_causal_loop_uses_real_resource_existing_graph_and_returns_to_schedule(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "full-loop.sqlite3", now=EVENING)
    player_id = _player(game)

    _wait(game, player_id, 1, "wait-01")
    assert _tick(db) == 1
    assert _runtime(db, "npc_mira")[1] == {
        "wood_stock": 2,
        "work_cycles": 0,
        "requested_wood": False,
    }

    _wait(game, player_id, 1, "wait-02")
    assert _runtime(db, "npc_mira")[1] == {
        "wood_stock": 1,
        "work_cycles": 1,
        "requested_wood": False,
    }

    _wait(game, player_id, 1, "wait-03")
    _wait(game, player_id, 1, "wait-04")
    mira_override, mira_state, _ = _runtime(db, "npc_mira")
    assert mira_state == {
        "wood_stock": 0,
        "work_cycles": 2,
        "requested_wood": False,
    }
    assert mira_override == 0

    _wait(game, player_id, 1, "wait-05")
    mira_override, mira_state, _ = _runtime(db, "npc_mira")
    kaspar_override, kaspar_state, _ = _runtime(db, "npc_kaspar")
    assert mira_override == 1
    assert mira_state["requested_wood"] is True
    assert kaspar_override == 1
    assert kaspar_state["goal"] == "collect_wood"
    assert _actor_location(db, "npc_kaspar") == "river_edge"
    assert _resource(db)[1] == "river_edge"
    assert _world_event_count(db, "NPC_REQUESTED_RESOURCE") == 1

    _wait(game, player_id, 1, "wait-06")
    kaspar_override, kaspar_state, _ = _runtime(db, "npc_kaspar")
    resource = _resource(db)
    assert kaspar_override == 1
    assert kaspar_state == {"carrying_wood": 1, "goal": "deliver_wood"}
    assert resource is not None
    assert resource[1] is None and resource[2] is None
    assert _world_event_count(db, "NPC_COLLECTED_RESOURCE") == 1

    _wait(game, player_id, 1, "wait-07")
    assert _actor_location(db, "npc_kaspar") == "village_square"
    _wait(game, player_id, 1, "wait-08")
    assert _actor_location(db, "npc_kaspar") == "workshop_yard"

    _wait(game, player_id, 1, "wait-09")
    assert _tick(db) == 9
    assert _runtime(db, "npc_mira")[:2] == (
        0,
        {"wood_stock": 1, "work_cycles": 2, "requested_wood": False},
    )
    assert _runtime(db, "npc_kaspar")[:2] == (
        0,
        {"carrying_wood": 0, "goal": None},
    )
    assert _actor_location(db, "npc_mira") == "workshop_yard"
    assert _actor_location(db, "npc_kaspar") == "village_square"
    assert _world_event_count(db, "NPC_DELIVERED_RESOURCE") == 1

    events = _events(db)
    assert [(event[0], event[1], event[2]) for event in events] == [
        (2, "npc_mira", "NPC_WORKED"),
        (4, "npc_mira", "NPC_WORKED"),
        (5, "npc_mira", "NPC_REQUESTED_RESOURCE"),
        (5, "npc_kaspar", "NPC_MOVED"),
        (6, "npc_kaspar", "NPC_COLLECTED_RESOURCE"),
        (7, "npc_kaspar", "NPC_MOVED"),
        (8, "npc_kaspar", "NPC_MOVED"),
        (9, "npc_kaspar", "NPC_DELIVERED_RESOURCE"),
    ]
    assert [event[4] for event in events if event[2] == "NPC_MOVED"] == [
        "river_edge",
        "village_square",
        "workshop_yard",
    ]


def test_missing_driftwood_blocks_chain_without_fabrication_or_duplicate_request(tmp_path: Path) -> None:
    db_path = tmp_path / "missing-resource.sqlite3"
    db, _, game, _ = _services(db_path, now=EVENING)
    player_id = _player(game)
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM entities WHERE id = 'driftwood_1'")
        conn.execute("COMMIT")

    result = _wait(game, player_id, 20, "wait-missing-resource")
    assert result.success is True
    assert _tick(db) == 20
    assert _resource(db) is None
    assert _world_event_count(db, "NPC_REQUESTED_RESOURCE") == 1
    assert _world_event_count(db, "NPC_COLLECTED_RESOURCE") == 0
    assert _world_event_count(db, "NPC_DELIVERED_RESOURCE") == 0
    assert _runtime(db, "npc_mira")[0] == 1
    assert _runtime(db, "npc_mira")[1]["requested_wood"] is True
    assert _runtime(db, "npc_kaspar")[0] == 1
    assert _runtime(db, "npc_kaspar")[1]["carrying_wood"] == 0

    db.initialize()
    assert _resource(db) is None


def test_wait_9_equals_nine_wait_1_for_all_autonomous_state(tmp_path: Path) -> None:
    db_a, _, game_a, _ = _services(tmp_path / "a.sqlite3", now=EVENING)
    db_b, _, game_b, _ = _services(tmp_path / "b.sqlite3", now=EVENING)
    player_a = _player(game_a, "qa-a")
    player_b = _player(game_b, "qa-b")

    result_a = _wait(game_a, player_a, 9, "wait-a-9")
    assert result_a.success is True
    for index in range(1, 10):
        result_b = _wait(game_b, player_b, 1, f"wait-b-{index}")
        assert result_b.success is True

    assert _living_snapshot(db_a) == _living_snapshot(db_b)


def test_restart_after_collection_preserves_state_and_finishes_delivery(tmp_path: Path) -> None:
    db_path = tmp_path / "restart.sqlite3"
    db, _, game, _ = _services(db_path, now=EVENING)
    player_id = _player(game, "qa-restart")

    assert _wait(game, player_id, 6, "wait-before-restart").success is True
    assert _tick(db) == 6
    assert _runtime(db, "npc_kaspar")[:2] == (
        1,
        {"carrying_wood": 1, "goal": "deliver_wood"},
    )
    resource = _resource(db)
    assert resource is not None and resource[1] is None and resource[2] is None

    reopened = GameDatabase(db_path)
    reopened.initialize()
    new_clock = FakeClock(EVENING)
    new_game = GameService(reopened, new_clock)

    assert _tick(reopened) == 6
    assert _runtime(reopened, "npc_kaspar")[1]["carrying_wood"] == 1
    resource = _resource(reopened)
    assert resource is not None and resource[1] is None and resource[2] is None

    assert _wait(new_game, player_id, 3, "wait-after-restart").success is True
    assert _tick(reopened) == 9
    assert _world_event_count(reopened, "NPC_COLLECTED_RESOURCE") == 1
    assert _world_event_count(reopened, "NPC_DELIVERED_RESOURCE") == 1
    assert _runtime(reopened, "npc_mira")[0] == 0
    assert _runtime(reopened, "npc_kaspar")[0] == 0
    assert _actor_location(reopened, "npc_kaspar") == "village_square"


def test_schedule_cannot_move_active_override_and_forced_pass_restores_after_goal(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "schedule.sqlite3", now=NOON)
    player_id = _player(game, "qa-schedule")

    assert _wait(game, player_id, 6, "wait-active-override").success is True
    assert _runtime(db, "npc_kaspar")[0] == 1
    assert _actor_location(db, "npc_kaspar") == "village_square"

    assert _wait(game, player_id, 2, "wait-finish-goal").success is True
    assert _runtime(db, "npc_kaspar")[0] == 0
    assert _runtime(db, "npc_mira")[0] == 0
    assert _actor_location(db, "npc_kaspar") == "river_edge"
    assert _actor_location(db, "npc_mira") == "workshop_yard"


def test_wait_records_one_player_event_and_autonomous_events_only_in_world_events(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "event-isolation.sqlite3", now=EVENING)
    player_id = _player(game, "qa-events")

    result = _wait(game, player_id, 9, "wait-event-isolation")
    assert result.success is True
    with db.connect() as conn:
        action_rows = conn.execute(
            "SELECT actor_id, action_type, external_id, success FROM action_events ORDER BY id"
        ).fetchall()
        autonomous_in_player_log = conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE action_type LIKE 'NPC_%'"
        ).fetchone()[0]
        world_event_count = conn.execute(
            "SELECT COUNT(*) FROM world_events"
        ).fetchone()[0]

    assert [tuple(row) for row in action_rows] == [
        (player_id, "WAIT", "wait-event-isolation", 1)
    ]
    assert autonomous_in_player_log == 0
    assert world_event_count == 8


def test_old_api_action_without_modifiers_still_works_and_wait_defaults_to_one(tmp_path: Path) -> None:
    db, _, _, client = _services(tmp_path / "api-compat.sqlite3", now=EVENING)
    player_id = _api_player(client)

    legacy = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "LOOK",
            "external_id": "legacy-look-no-modifiers",
        },
    )
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["success"] is True

    waited = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "WAIT",
            "external_id": "wait-default-one",
        },
    )
    assert waited.status_code == 200, waited.text
    assert waited.json()["success"] is True
    assert _tick(db) == 1


@pytest.mark.parametrize("ticks", [1, 60])
def test_api_accepts_only_valid_wait_range(tmp_path: Path, ticks: int) -> None:
    db, _, _, client = _services(tmp_path / f"valid-{ticks}.sqlite3", now=EVENING)
    player_id = _api_player(client, f"qa-valid-{ticks}")

    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "WAIT",
            "modifiers": {"ticks": ticks},
            "external_id": f"valid-wait-{ticks}",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert _tick(db) == ticks


@pytest.mark.parametrize("ticks", [0, 61, -1, "9", 9.5, True])
def test_invalid_wait_payloads_do_not_mutate_simulation(tmp_path: Path, ticks) -> None:
    db, _, _, client = _services(tmp_path / f"invalid-{repr(ticks)}.sqlite3", now=EVENING)
    player_id = _api_player(client, f"qa-invalid-{repr(ticks)}")
    before = _simulation_snapshot_for_invalid(db)

    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "WAIT",
            "modifiers": {"ticks": ticks},
            "external_id": f"invalid-wait-{repr(ticks)}",
        },
    )
    assert response.status_code in {200, 400, 422}, response.text
    if response.status_code == 200:
        payload = response.json()
        assert payload["success"] is False, payload

    assert _simulation_snapshot_for_invalid(db) == before


def test_malformed_api_payload_does_not_mutate_simulation(tmp_path: Path) -> None:
    db, _, _, client = _services(tmp_path / "malformed.sqlite3", now=EVENING)
    player_id = _api_player(client, "qa-malformed")
    before = _simulation_snapshot_for_invalid(db)

    response = client.post(
        "/api/action",
        json={
            "player_id": player_id,
            "action_type": "WAIT",
            "modifiers": ["not", "an", "object"],
        },
    )
    assert response.status_code == 422, response.text
    assert _simulation_snapshot_for_invalid(db) == before


def test_database_integrity_after_full_loop(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "integrity.sqlite3", now=EVENING)
    player_id = _player(game, "qa-integrity")
    assert _wait(game, player_id, 9, "wait-integrity").success is True

    with db.connect() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute(
            "SELECT COUNT(*) FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_runtime_state WHERE npc_actor_id = 'npc_mira'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_runtime_state WHERE npc_actor_id = 'npc_kaspar'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM entities WHERE id = 'driftwood_1'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events WHERE event_type = 'NPC_REQUESTED_RESOURCE'"
        ).fetchone()[0] == 1
        positions = dict(
            conn.execute(
                "SELECT id, location_id FROM actors WHERE id IN ('npc_mira', 'npc_kaspar')"
            ).fetchall()
        )
    assert positions == {"npc_mira": "workshop_yard", "npc_kaspar": "village_square"}


def test_duplicate_wait_external_id_is_replayed_without_advancing_twice(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "idempotent.sqlite3", now=EVENING)
    player_id = _player(game, "qa-idempotent")

    first = _wait(game, player_id, 9, "same-wait-id")
    replay = _wait(game, player_id, 9, "same-wait-id")
    assert first.success is True
    assert replay.success is True
    assert replay.replayed is True
    assert replay.event_id == first.event_id
    assert _tick(db) == 9
    assert len(_events(db)) == 8
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE external_id = 'same-wait-id'"
        ).fetchone()[0] == 1


def test_player_take_before_kaspar_blocks_collection_without_duplication(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "take-before.sqlite3", now=EVENING)
    player_id = _player(game, "qa-take-before")

    for destination, external_id in [
        ("village_square", "move-to-square"),
        ("river_edge", "move-to-river"),
    ]:
        moved = game.execute(
            CanonicalAction(
                actor_id=player_id,
                action_type=ActionType.MOVE,
                destination_id=destination,
            ),
            external_id=external_id,
        )
        assert moved.success is True
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="driftwood_1",
        ),
        external_id="player-takes-driftwood",
    )
    assert taken.success is True

    assert _wait(game, player_id, 9, "wait-after-player-take").success is True
    resource = _resource(db)
    assert resource is not None
    assert resource[1] is None and resource[2] == player_id
    assert _world_event_count(db, "NPC_COLLECTED_RESOURCE") == 0
    assert _world_event_count(db, "NPC_DELIVERED_RESOURCE") == 0
    assert _world_event_count(db, "NPC_REQUESTED_RESOURCE") == 1


def test_player_take_after_kaspar_collection_cannot_duplicate_resource(tmp_path: Path) -> None:
    db, _, game, _ = _services(tmp_path / "take-after.sqlite3", now=NOON)
    player_id = _player(game, "qa-take-after")

    assert _wait(game, player_id, 5, "wait-until-collected").success is True
    assert _runtime(db, "npc_kaspar")[1]["carrying_wood"] == 1
    assert _world_event_count(db, "NPC_COLLECTED_RESOURCE") == 1

    for destination, external_id in [
        ("village_square", "move-after-square"),
        ("river_edge", "move-after-river"),
    ]:
        moved = game.execute(
            CanonicalAction(
                actor_id=player_id,
                action_type=ActionType.MOVE,
                destination_id=destination,
            ),
            external_id=external_id,
        )
        assert moved.success is True
    take = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="driftwood_1",
        ),
        external_id="take-after-kaspar",
    )
    assert take.success is False
    assert take.code in {"TARGET_NOT_PRESENT", "ALREADY_OWNED"}

    resource = _resource(db)
    assert resource is not None and resource[1] is None and resource[2] is None
    assert _runtime(db, "npc_kaspar")[1]["carrying_wood"] == 1
    assert _world_event_count(db, "NPC_COLLECTED_RESOURCE") == 1
