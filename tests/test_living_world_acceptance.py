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
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService
from samseberpg.server import build_app

NOON = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def services(path: Path, now: datetime = EVENING):
    db = GameDatabase(path)
    db.initialize()
    clock = FakeClock(now)
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest)
    return db, game, TestClient(create_app(game, quest, dialogue))


def player(game: GameService, key: str = "qa") -> str:
    return game.register_player(key, "QA Player")


def api_player(client: TestClient, key: str = "qa-api") -> str:
    response = client.post("/api/session", json={"external_id": key, "name": "QA"})
    assert response.status_code == 200, response.text
    return str(response.json()["player_id"])


def wait(game: GameService, player_id: str, ticks: int, external_id: str):
    return game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": ticks},
        ),
        external_id=external_id,
    )


def runtime(db: GameDatabase, npc: str):
    with db.connect() as conn:
        row = conn.execute(
            "SELECT override_active,state_json,updated_tick FROM npc_runtime_state WHERE npc_actor_id=?",
            (npc,),
        ).fetchone()
    assert row is not None
    return int(row[0]), json.loads(str(row[1])), int(row[2])


def tick(db: GameDatabase) -> int:
    with db.connect() as conn:
        row = conn.execute("SELECT tick FROM world_runtime WHERE world_id=?", (DEFAULT_WORLD_ID,)).fetchone()
    assert row is not None
    return int(row[0])


def location(db: GameDatabase, actor: str) -> str | None:
    with db.connect() as conn:
        row = conn.execute("SELECT location_id FROM actors WHERE id=?", (actor,)).fetchone()
    assert row is not None
    return None if row[0] is None else str(row[0])


def resource(db: GameDatabase):
    with db.connect() as conn:
        return conn.execute(
            "SELECT id,location_id,owner_actor_id,state_json FROM entities WHERE id='driftwood_1'"
        ).fetchone()


def events(db: GameDatabase):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT tick,actor_id,event_type,target_id,location_id,data_json FROM world_events ORDER BY id"
        ).fetchall()
    return [
        (
            int(r[0]), str(r[1]), str(r[2]),
            None if r[3] is None else str(r[3]),
            None if r[4] is None else str(r[4]),
            json.loads(str(r[5])),
        )
        for r in rows
    ]


def count_event(db: GameDatabase, event_type: str) -> int:
    with db.connect() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM world_events WHERE event_type=?", (event_type,)
        ).fetchone()[0])


def snapshot(db: GameDatabase):
    with db.connect() as conn:
        rs = conn.execute(
            "SELECT npc_actor_id,override_active,state_json,updated_tick FROM npc_runtime_state ORDER BY npc_actor_id"
        ).fetchall()
        actors = conn.execute(
            "SELECT actors.id,actors.location_id,npcs.current_activity FROM npcs "
            "JOIN actors ON actors.id=npcs.actor_id WHERE actors.id IN ('npc_mira','npc_kaspar') ORDER BY actors.id"
        ).fetchall()
        item = conn.execute(
            "SELECT id,location_id,owner_actor_id,state_json FROM entities WHERE id='driftwood_1'"
        ).fetchone()
    return {
        "tick": tick(db),
        "runtime": [(str(r[0]), int(r[1]), json.loads(str(r[2])), int(r[3])) for r in rs],
        "actors": [(str(r[0]), r[1], str(r[2])) for r in actors],
        "resource": None if item is None else (str(item[0]), item[1], item[2], json.loads(str(item[3]))),
        "events": events(db),
    }


def simulation_state(db: GameDatabase):
    with db.connect() as conn:
        actors = [tuple(r) for r in conn.execute("SELECT id,location_id FROM actors ORDER BY id")]
        entities = [tuple(r) for r in conn.execute(
            "SELECT id,location_id,owner_actor_id,state_json FROM entities ORDER BY id"
        )]
    return snapshot(db), actors, entities


def test_bootstrap_runtime_and_real_resource(tmp_path: Path) -> None:
    db, _, _ = services(tmp_path / "bootstrap.sqlite3")
    assert tick(db) == 0
    assert runtime(db, "npc_mira") == (0, {"wood_stock": 2, "work_cycles": 0, "requested_wood": False}, 0)
    assert runtime(db, "npc_kaspar") == (0, {"carrying_wood": 0, "goal": None}, 0)
    item = resource(db)
    assert item is not None
    assert tuple(item[:3]) == ("driftwood_1", "river_edge", None)
    assert json.loads(str(item[3])) == {"resource_kind": "useful_wood"}


def test_full_causal_loop_exact_event_sequence_and_schedule_restore(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "loop.sqlite3", EVENING)
    p = player(game)
    for i in range(1, 10):
        result = wait(game, p, 1, f"wait-{i}")
        assert result.success is True
        if i == 2:
            assert runtime(db, "npc_mira")[1]["wood_stock"] == 1
        if i == 4:
            assert runtime(db, "npc_mira")[1] == {"wood_stock": 0, "work_cycles": 2, "requested_wood": False}
        if i == 5:
            assert runtime(db, "npc_mira")[0] == 1
            assert runtime(db, "npc_kaspar")[1]["goal"] == "collect_wood"
            assert count_event(db, "NPC_REQUESTED_RESOURCE") == 1
        if i == 6:
            assert runtime(db, "npc_kaspar")[1]["carrying_wood"] == 1
            item = resource(db)
            assert item is not None and item[1] is None and item[2] is None
    assert tick(db) == 9
    assert runtime(db, "npc_mira")[:2] == (0, {"wood_stock": 1, "work_cycles": 2, "requested_wood": False})
    assert runtime(db, "npc_kaspar")[:2] == (0, {"carrying_wood": 0, "goal": None})
    assert location(db, "npc_mira") == "workshop_yard"
    assert location(db, "npc_kaspar") == "village_square"
    assert [(e[0], e[1], e[2]) for e in events(db)] == [
        (2, "npc_mira", "NPC_WORKED"),
        (4, "npc_mira", "NPC_WORKED"),
        (5, "npc_mira", "NPC_REQUESTED_RESOURCE"),
        (5, "npc_kaspar", "NPC_MOVED"),
        (6, "npc_kaspar", "NPC_COLLECTED_RESOURCE"),
        (7, "npc_kaspar", "NPC_MOVED"),
        (8, "npc_kaspar", "NPC_MOVED"),
        (9, "npc_kaspar", "NPC_DELIVERED_RESOURCE"),
    ]
    assert [e[4] for e in events(db) if e[2] == "NPC_MOVED"] == ["river_edge", "village_square", "workshop_yard"]


def test_missing_resource_never_fabricates_or_repeats_request_and_does_not_respawn(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"
    db, game, _ = services(path)
    p = player(game, "missing")
    with db.connect() as conn:
        conn.execute("DELETE FROM entities WHERE id='driftwood_1'")
    assert wait(game, p, 20, "wait-missing").success is True
    assert resource(db) is None
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events "
            "WHERE event_type='NPC_REQUESTED_RESOURCE' "
            "AND actor_id='npc_mira' AND target_id='driftwood_1'"
        ).fetchone()[0] == 1
    assert count_event(db, "NPC_COLLECTED_RESOURCE") == 0
    assert count_event(db, "NPC_DELIVERED_RESOURCE") == 0
    db.initialize()
    assert resource(db) is None


def test_wait_9_equals_nine_wait_1(tmp_path: Path) -> None:
    db_a, game_a, _ = services(tmp_path / "a.sqlite3")
    db_b, game_b, _ = services(tmp_path / "b.sqlite3")
    pa, pb = player(game_a, "a"), player(game_b, "b")
    assert wait(game_a, pa, 9, "a9").success is True
    for i in range(9):
        assert wait(game_b, pb, 1, f"b{i}").success is True
    assert snapshot(db_a) == snapshot(db_b)


def test_restart_after_collection_preserves_and_completes(tmp_path: Path) -> None:
    path = tmp_path / "restart.sqlite3"
    db, game, _ = services(path)
    p = player(game, "restart")
    assert wait(game, p, 6, "before-restart").success is True
    assert runtime(db, "npc_kaspar")[:2] == (1, {"carrying_wood": 1, "goal": "deliver_wood"})
    GameDatabase(path).initialize()
    reopened = GameDatabase(path)
    new_game = GameService(reopened, FakeClock(EVENING), living_world=LivingWorldService())
    assert tick(reopened) == 6
    item = resource(reopened)
    assert item is not None and item[1] is None and item[2] is None
    assert wait(new_game, p, 3, "after-restart").success is True
    assert tick(reopened) == 9
    assert count_event(reopened, "NPC_COLLECTED_RESOURCE") == 1
    assert count_event(reopened, "NPC_DELIVERED_RESOURCE") == 1


def test_schedule_override_blocks_wall_clock_then_forced_pass_restores(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "schedule.sqlite3", NOON)
    p = player(game, "schedule")
    assert wait(game, p, 6, "active").success is True
    assert runtime(db, "npc_kaspar")[0] == 1
    assert location(db, "npc_kaspar") == "village_square"
    assert wait(game, p, 2, "finish").success is True
    assert runtime(db, "npc_kaspar")[0] == 0
    assert location(db, "npc_kaspar") == "river_edge"


def test_event_isolation_one_player_wait_only(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "events.sqlite3")
    p = player(game, "events")
    assert wait(game, p, 9, "one-wait").success is True
    with db.connect() as conn:
        rows = conn.execute("SELECT actor_id,action_type,external_id,success FROM action_events ORDER BY id").fetchall()
        npc_rows = conn.execute("SELECT COUNT(*) FROM action_events WHERE action_type LIKE 'NPC_%'").fetchone()[0]
    assert [tuple(r) for r in rows] == [(p, "WAIT", "one-wait", 1)]
    assert npc_rows == 0
    assert len(events(db)) == 8


def test_api_backward_compat_and_default_wait(tmp_path: Path) -> None:
    db, _, client = services(tmp_path / "api.sqlite3")
    p = api_player(client)
    legacy = client.post("/api/action", json={"player_id": p, "action_type": "LOOK", "external_id": "look"})
    assert legacy.status_code == 200 and legacy.json()["success"] is True
    default_wait = client.post("/api/action", json={"player_id": p, "action_type": "WAIT", "external_id": "wait"})
    assert default_wait.status_code == 200 and default_wait.json()["success"] is True
    assert tick(db) == 1


@pytest.mark.parametrize("ticks", [1, 60])
def test_api_valid_wait_boundaries(tmp_path: Path, ticks: int) -> None:
    db, _, client = services(tmp_path / f"valid-{ticks}.sqlite3")
    p = api_player(client, f"valid-{ticks}")
    response = client.post("/api/action", json={
        "player_id": p, "action_type": "WAIT", "modifiers": {"ticks": ticks}, "external_id": f"w{ticks}"
    })
    assert response.status_code == 200 and response.json()["success"] is True
    assert tick(db) == ticks


@pytest.mark.parametrize("ticks", [0, 61, -1, "9", 9.5, True])
def test_api_invalid_wait_values_do_not_mutate(tmp_path: Path, ticks) -> None:
    db, _, client = services(tmp_path / f"invalid-{type(ticks).__name__}-{str(ticks)}.sqlite3")
    p = api_player(client, f"invalid-{type(ticks).__name__}-{str(ticks)}")
    before = simulation_state(db)
    response = client.post("/api/action", json={
        "player_id": p, "action_type": "WAIT", "modifiers": {"ticks": ticks}, "external_id": "bad"
    })
    assert response.status_code in {200, 400, 422}, response.text
    if response.status_code == 200:
        assert response.json()["success"] is False
    assert simulation_state(db) == before


def test_api_malformed_modifiers_do_not_mutate(tmp_path: Path) -> None:
    db, _, client = services(tmp_path / "malformed.sqlite3")
    p = api_player(client, "malformed")
    before = simulation_state(db)
    response = client.post("/api/action", json={"player_id": p, "action_type": "WAIT", "modifiers": ["bad"]})
    assert response.status_code in {200, 400, 422}, response.text
    if response.status_code == 200:
        assert response.json()["success"] is False
    assert simulation_state(db) == before


def test_official_build_app_wires_wait(tmp_path: Path) -> None:
    path = tmp_path / "official.sqlite3"
    client = TestClient(build_app(path))
    p = api_player(client, "official")
    response = client.post("/api/action", json={
        "player_id": p, "action_type": "WAIT", "modifiers": {"ticks": 1}, "external_id": "official-wait"
    })
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert tick(GameDatabase(path)) == 1


def test_database_integrity_and_no_duplicates_after_loop(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "integrity.sqlite3")
    p = player(game, "integrity")
    assert wait(game, p, 9, "integrity-wait").success is True
    with db.connect() as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("SELECT COUNT(*) FROM world_runtime WHERE world_id=?", (DEFAULT_WORLD_ID,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM npc_runtime_state WHERE npc_actor_id='npc_mira'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM npc_runtime_state WHERE npc_actor_id='npc_kaspar'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM entities WHERE id='driftwood_1'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM world_events WHERE event_type='NPC_REQUESTED_RESOURCE'").fetchone()[0] == 1


def test_wait_external_id_replay_does_not_advance_twice(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "replay.sqlite3")
    p = player(game, "replay")
    first = wait(game, p, 9, "same")
    second = wait(game, p, 9, "same")
    assert first.success is True and second.replayed is True and second.event_id == first.event_id
    assert tick(db) == 9 and len(events(db)) == 8


def test_player_take_before_kaspar_blocks_collection(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "take-before.sqlite3")
    p = player(game, "take-before")
    for dest in ("village_square", "river_edge"):
        assert game.execute(CanonicalAction(p, ActionType.MOVE, destination_id=dest)).success is True
    assert game.execute(CanonicalAction(p, ActionType.TAKE, target_id="driftwood_1")).success is True
    assert wait(game, p, 9, "after-take").success is True
    item = resource(db)
    assert item is not None and item[2] == p
    assert count_event(db, "NPC_COLLECTED_RESOURCE") == 0
    assert count_event(db, "NPC_DELIVERED_RESOURCE") == 0


def test_player_take_after_kaspar_collection_cannot_duplicate(tmp_path: Path) -> None:
    db, game, _ = services(tmp_path / "take-after.sqlite3", NOON)
    p = player(game, "take-after")
    assert wait(game, p, 5, "collect").success is True
    assert count_event(db, "NPC_COLLECTED_RESOURCE") == 1
    for dest in ("village_square", "river_edge"):
        assert game.execute(CanonicalAction(p, ActionType.MOVE, destination_id=dest)).success is True
    result = game.execute(CanonicalAction(p, ActionType.TAKE, target_id="driftwood_1"))
    assert result.success is False
    assert resource(db)[1] is None and resource(db)[2] is None
    assert count_event(db, "NPC_COLLECTED_RESOURCE") == 1


def test_reinitialize_preserves_runtime_and_consumed_resource(tmp_path: Path) -> None:
    path = tmp_path / "reinit.sqlite3"
    db, game, _ = services(path)
    p = player(game, "reinit")
    assert wait(game, p, 6, "consume").success is True
    before = snapshot(db)
    db.initialize()
    after = snapshot(db)
    assert after == before
