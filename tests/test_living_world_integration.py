from __future__ import annotations

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


class StubLivingWorld:
    def __init__(self, *, clear_override_actor_id: str | None = None) -> None:
        self.calls: list[int] = []
        self.clear_override_actor_id = clear_override_actor_id

    def advance(self, conn, ticks: int) -> list[dict[str, object]]:
        self.calls.append(ticks)
        events: list[dict[str, object]] = []
        for _ in range(ticks):
            current = int(
                conn.execute(
                    "SELECT tick FROM world_runtime WHERE world_id = ?",
                    (DEFAULT_WORLD_ID,),
                ).fetchone()[0]
            )
            next_tick = current + 1
            conn.execute(
                "UPDATE world_runtime SET tick = ? WHERE world_id = ?",
                (next_tick, DEFAULT_WORLD_ID),
            )
            conn.execute(
                "INSERT INTO world_events "
                "(world_id, tick, actor_id, event_type, target_id, location_id, data_json, summary) "
                "VALUES (?, ?, 'npc_kaspar', 'NPC_MOVED', NULL, 'river_edge', '{}', ?)",
                (DEFAULT_WORLD_ID, next_tick, f"stub tick {next_tick}"),
            )
            events.append({"tick": next_tick, "event_type": "NPC_MOVED"})

        if self.clear_override_actor_id is not None:
            conn.execute(
                "UPDATE npc_runtime_state SET override_active = 0 WHERE npc_actor_id = ?",
                (self.clear_override_actor_id,),
            )
        return events


class OfflineProvider:
    def generate(self, context):
        raise RuntimeError("offline")


def install_runtime_contract(db: GameDatabase) -> None:
    with db.connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS world_runtime (
                world_id TEXT PRIMARY KEY,
                tick INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS npc_runtime_state (
                npc_actor_id TEXT PRIMARY KEY,
                override_active INTEGER NOT NULL DEFAULT 0,
                state_json TEXT NOT NULL DEFAULT '{}',
                updated_tick INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS world_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                world_id TEXT NOT NULL,
                tick INTEGER NOT NULL,
                actor_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                target_id TEXT,
                location_id TEXT,
                data_json TEXT NOT NULL DEFAULT '{}',
                summary TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO world_runtime (world_id, tick) VALUES (?, 0)",
            (DEFAULT_WORLD_ID,),
        )
        conn.executemany(
            "INSERT OR IGNORE INTO npc_runtime_state "
            "(npc_actor_id, override_active, state_json, updated_tick) VALUES (?, 0, '{}', 0)",
            [("npc_mira",), ("npc_kaspar",)],
        )


def make_game(
    db_path: Path,
    *,
    now: datetime | None = None,
    living_world: StubLivingWorld | None = None,
) -> tuple[GameDatabase, GameService, StubLivingWorld]:
    db = GameDatabase(db_path)
    db.initialize()
    install_runtime_contract(db)
    clock = FakeClock(now or datetime(2026, 8, 28, 12, 0, tzinfo=timezone.utc))
    service = living_world or StubLivingWorld()
    return db, GameService(db, clock, living_world=service), service


def runtime_snapshot(db: GameDatabase) -> tuple[object, ...]:
    with db.connect() as conn:
        tick = conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0]
        locations = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT id, location_id FROM actors WHERE actor_type = 'npc' ORDER BY id"
            ).fetchall()
        )
        overrides = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT npc_actor_id, override_active, state_json, updated_tick "
                "FROM npc_runtime_state ORDER BY npc_actor_id"
            ).fetchall()
        )
        world_event_count = conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0]
        action_event_count = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        last_simulated_at = conn.execute(
            "SELECT last_simulated_at FROM worlds WHERE id = ?", (DEFAULT_WORLD_ID,)
        ).fetchone()[0]
    return tick, locations, overrides, world_event_count, action_event_count, last_simulated_at


def test_wait_defaults_to_one_tick_and_records_one_player_event(tmp_path: Path) -> None:
    db, game, living_world = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")

    result = game.execute(CanonicalAction(actor_id=player, action_type=ActionType.WAIT))

    assert result.success is True
    assert result.code == "OK"
    assert living_world.calls == [1]
    with db.connect() as conn:
        assert conn.execute("SELECT tick FROM world_runtime").fetchone()[0] == 1
        player_events = conn.execute(
            "SELECT action_type, success FROM action_events WHERE actor_id = ?", (player,)
        ).fetchall()
        world_events = conn.execute(
            "SELECT tick, event_type FROM world_events ORDER BY id"
        ).fetchall()
    assert [tuple(row) for row in player_events] == [("WAIT", 1)]
    assert [tuple(row) for row in world_events] == [(1, "NPC_MOVED")]


def test_wait_nine_advances_once_with_nine_ticks(tmp_path: Path) -> None:
    db, game, living_world = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")

    result = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 9},
        )
    )

    assert result.success is True
    assert living_world.calls == [9]
    with db.connect() as conn:
        assert conn.execute("SELECT tick FROM world_runtime").fetchone()[0] == 9
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE actor_id = ? AND action_type = 'WAIT'",
            (player,),
        ).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 9


def _run_wait_sequence(db_path: Path, waits: list[int]) -> tuple[object, ...]:
    db, game, _ = make_game(db_path)
    player = game.register_player(f"discord-{db_path.stem}", "Ari")
    for index, ticks in enumerate(waits):
        result = game.execute(
            CanonicalAction(
                actor_id=player,
                action_type=ActionType.WAIT,
                modifiers={"ticks": ticks},
            ),
            external_id=f"wait-{index}",
        )
        assert result.success is True
    with db.connect() as conn:
        tick = conn.execute("SELECT tick FROM world_runtime").fetchone()[0]
        world_events = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT tick, actor_id, event_type, target_id, location_id, data_json, summary "
                "FROM world_events ORDER BY id"
            ).fetchall()
        )
        npc_locations = tuple(
            tuple(row)
            for row in conn.execute(
                "SELECT id, location_id FROM actors WHERE actor_type = 'npc' ORDER BY id"
            ).fetchall()
        )
    return tick, world_events, npc_locations


def test_wait_nine_matches_nine_wait_one_calls(tmp_path: Path) -> None:
    batched = _run_wait_sequence(tmp_path / "batched.sqlite3", [9])
    sequential = _run_wait_sequence(tmp_path / "sequential.sqlite3", [1] * 9)

    assert batched == sequential


@pytest.mark.parametrize(
    "modifiers",
    [
        {"ticks": 0},
        {"ticks": -1},
        {"ticks": 61},
        {"ticks": 1.5},
        {"ticks": "1"},
        {"ticks": True},
        [],
        "ticks=1",
        {"ticks": {"bad": 1}},
    ],
)
def test_invalid_wait_is_deterministic_and_does_not_mutate_runtime(
    tmp_path: Path, modifiers: object
) -> None:
    db, game, living_world = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")
    before = runtime_snapshot(db)

    result = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.WAIT,
            modifiers=modifiers,  # type: ignore[arg-type]
        )
    )

    assert result.success is False
    assert result.code == "INVALID_WAIT_TICKS"
    assert result.event_id is None
    assert living_world.calls == []
    assert runtime_snapshot(db) == before


def test_active_override_blocks_normal_schedule_movement(tmp_path: Path) -> None:
    db, game, _ = make_game(
        tmp_path / "world.sqlite3",
        now=datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc),
    )
    player = game.register_player("discord-a", "Ari")
    with db.connect() as conn:
        conn.execute(
            "UPDATE actors SET location_id = 'river_edge' WHERE id = 'npc_kaspar'"
        )
        conn.execute(
            "UPDATE npc_runtime_state SET override_active = 1 WHERE npc_actor_id = 'npc_kaspar'"
        )

    game.observe(player)

    with db.connect() as conn:
        kaspar = conn.execute(
            "SELECT actors.location_id, npcs.current_activity FROM actors "
            "JOIN npcs ON npcs.actor_id = actors.id WHERE actors.id = 'npc_kaspar'"
        ).fetchone()
    assert tuple(kaspar) == ("river_edge", "checking the riverbank")


def test_wait_forced_schedule_pass_restores_npc_after_override_clears(tmp_path: Path) -> None:
    living_world = StubLivingWorld(clear_override_actor_id="npc_kaspar")
    db, game, _ = make_game(
        tmp_path / "world.sqlite3",
        now=datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc),
        living_world=living_world,
    )
    player = game.register_player("discord-a", "Ari")
    with db.connect() as conn:
        conn.execute(
            "UPDATE actors SET location_id = 'river_edge' WHERE id = 'npc_kaspar'"
        )
        conn.execute(
            "UPDATE npcs SET current_activity = 'autonomous collection' WHERE actor_id = 'npc_kaspar'"
        )
        conn.execute(
            "UPDATE npc_runtime_state SET override_active = 1 WHERE npc_actor_id = 'npc_kaspar'"
        )

    result = game.execute(CanonicalAction(actor_id=player, action_type=ActionType.WAIT))

    assert result.success is True
    with db.connect() as conn:
        kaspar = conn.execute(
            "SELECT actors.location_id, npcs.current_activity FROM actors "
            "JOIN npcs ON npcs.actor_id = actors.id WHERE actors.id = 'npc_kaspar'"
        ).fetchone()
        override = conn.execute(
            "SELECT override_active FROM npc_runtime_state WHERE npc_actor_id = 'npc_kaspar'"
        ).fetchone()[0]
    assert override == 0
    assert tuple(kaspar) == ("village_square", "trading gathered goods")


def test_wait_replay_does_not_advance_autonomous_world_twice(tmp_path: Path) -> None:
    db, game, living_world = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")
    action = CanonicalAction(
        actor_id=player,
        action_type=ActionType.WAIT,
        modifiers={"ticks": 3},
    )

    first = game.execute(action, external_id="wait-once")
    replay = game.execute(action, external_id="wait-once")

    assert first.success is True
    assert replay.replayed is True
    assert replay.event_id == first.event_id
    assert living_world.calls == [3]
    with db.connect() as conn:
        assert conn.execute("SELECT tick FROM world_runtime").fetchone()[0] == 3
        assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 3
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE action_type = 'WAIT'"
        ).fetchone()[0] == 1


def test_existing_look_and_move_behaviors_remain_unchanged(tmp_path: Path) -> None:
    _, game, living_world = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")

    looked = game.execute(CanonicalAction(actor_id=player, action_type=ActionType.LOOK))
    moved = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.MOVE,
            destination_id="village_square",
        )
    )

    assert looked.success is True
    assert moved.success is True
    assert game.observe(player).location_id == "village_square"
    assert living_world.calls == []


def test_api_action_is_backwards_compatible_and_accepts_wait_modifiers(tmp_path: Path) -> None:
    db, game, living_world = make_game(tmp_path / "world.sqlite3")
    quest = QuestService(db, game.clock)
    dialogue = DialogueService(db, quest, provider=OfflineProvider())
    client = TestClient(create_app(game, quest, dialogue))
    player = client.post(
        "/api/session", json={"external_id": "api-player", "name": "Ren"}
    ).json()["player_id"]

    legacy = client.post(
        "/api/action",
        json={"player_id": player, "action_type": "LOOK", "external_id": "legacy-look"},
    )
    waited = client.post(
        "/api/action",
        json={
            "player_id": player,
            "action_type": "WAIT",
            "modifiers": {"ticks": 9},
            "external_id": "api-wait",
        },
    )

    assert legacy.status_code == 200
    assert legacy.json()["success"] is True
    assert waited.status_code == 200
    payload = waited.json()
    assert payload["success"] is True
    assert payload["code"] == "OK"
    assert set(payload) == {"success", "code", "summary", "event_id", "replayed"}
    assert living_world.calls == [9]


def test_api_invalid_wait_structure_returns_action_failure_without_mutation(tmp_path: Path) -> None:
    db, game, living_world = make_game(tmp_path / "world.sqlite3")
    quest = QuestService(db, game.clock)
    dialogue = DialogueService(db, quest, provider=OfflineProvider())
    client = TestClient(create_app(game, quest, dialogue))
    player = client.post(
        "/api/session", json={"external_id": "api-player", "name": "Ren"}
    ).json()["player_id"]
    before = runtime_snapshot(db)

    response = client.post(
        "/api/action",
        json={"player_id": player, "action_type": "WAIT", "modifiers": ["ticks", 9]},
    )

    assert response.status_code == 200
    assert response.json()["code"] == "INVALID_WAIT_TICKS"
    assert response.json()["event_id"] is None
    assert living_world.calls == []
    assert runtime_snapshot(db) == before
