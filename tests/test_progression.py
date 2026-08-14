import json
import sqlite3
from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase, SCHEMA_VERSION
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.progression import ACHIEVEMENTS, ABILITIES, ProgressionEngine


class NoopProgressionEngine:
    def evaluate_after_event(self, conn, player_id, event_id, now_text):
        return ()


def make_game(tmp_path, *, with_progression=False):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    engine = None if with_progression else NoopProgressionEngine()
    return db, GameService(db, FakeClock(now), progression_engine=engine)


def test_schema_v3_contains_progression_tables_and_catalog():
    assert SCHEMA_VERSION == 3
    assert ACHIEVEMENTS["THROWING_HABIT_1"].name == "Рука помнит дугу"
    assert ABILITIES["STEADY_HAND"].name == "Твёрдая рука"


def test_migration_v2_to_v3_preserves_existing_rows(tmp_path):
    path = tmp_path / "v2.db"
    at = "2026-08-14T08:00:00+00:00"
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            """
            CREATE TABLE worlds (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, timezone TEXT NOT NULL,
                created_at TEXT NOT NULL, last_simulated_at TEXT NOT NULL
            );
            CREATE TABLE locations (
                id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
                name TEXT NOT NULL, description TEXT NOT NULL, sort_order INTEGER NOT NULL
            );
            CREATE TABLE actors (
                id TEXT PRIMARY KEY, world_id TEXT NOT NULL REFERENCES worlds(id),
                actor_type TEXT NOT NULL, name TEXT NOT NULL,
                location_id TEXT NOT NULL REFERENCES locations(id), created_at TEXT NOT NULL
            );
            CREATE TABLE players (
                actor_id TEXT PRIMARY KEY REFERENCES actors(id),
                discord_user_id TEXT NOT NULL UNIQUE, joined_at TEXT NOT NULL,
                coins INTEGER NOT NULL DEFAULT 10
            );
            CREATE TABLE action_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                world_id TEXT NOT NULL REFERENCES worlds(id), external_id TEXT,
                occurred_at TEXT NOT NULL, actor_id TEXT NOT NULL,
                action_type TEXT NOT NULL, target_id TEXT, location_id TEXT,
                success INTEGER NOT NULL, result_code TEXT NOT NULL,
                summary TEXT NOT NULL, evidence_json TEXT NOT NULL DEFAULT '{}'
            );
            """
        )
        conn.execute("INSERT INTO worlds VALUES ('village_1','Legacy','UTC',?,?)", (at, at))
        conn.execute("INSERT INTO locations VALUES ('village_square','village_1','Square','Legacy square',1)")
        conn.execute("INSERT INTO actors VALUES ('player_old','village_1','player','Old','village_square',?)", (at,))
        conn.execute("INSERT INTO players VALUES ('player_old','old-discord',?,9)", (at,))
        conn.execute(
            """
            INSERT INTO action_events(
                world_id, occurred_at, actor_id, action_type, success,
                result_code, summary, evidence_json
            ) VALUES ('village_1', ?, 'player_old', 'LOOK', 1, 'OK', 'old event', '{}')
            """,
            (at,),
        )
        conn.execute("PRAGMA user_version = 2")
        conn.commit()

    db = GameDatabase(path)
    db.initialize()
    with db.connect() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "player_achievements" in tables
        assert "player_abilities" in tables
        assert conn.execute("SELECT coins FROM players WHERE actor_id='player_old'").fetchone()[0] == 9
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1


def execute_and_evaluate(db, game, engine, action, external_id):
    result = game.execute(action, external_id=external_id)
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        unlocks = engine.evaluate_after_event(
            conn, action.actor_id, result.event_id, "2026-08-14T08:10:00+00:00"
        )
        conn.commit()
    return result, unlocks


def prepare_player_on_square_with_flat_stone(game):
    player = game.register_player("discord-progress", "Thrower")
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
    return player


def test_three_throws_with_only_one_projectile_do_not_unlock(tmp_path):
    db, game = make_game(tmp_path)
    engine = ProgressionEngine()
    player = prepare_player_on_square_with_flat_stone(game)
    for index in range(3):
        result, unlocks = execute_and_evaluate(
            db,
            game,
            engine,
            CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
            f"same-throw-{index}",
        )
        assert result.success
        assert unlocks == ()
        if index < 2:
            assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM player_achievements").fetchone()[0] == 0


def test_three_successful_throws_with_two_projectiles_unlock_once_with_evidence(tmp_path):
    db, game = make_game(tmp_path)
    engine = ProgressionEngine()
    player = prepare_player_on_square_with_flat_stone(game)

    first, unlocks = execute_and_evaluate(
        db, game, engine,
        CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
        "variety-1",
    )
    assert first.success and unlocks == ()
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    second, unlocks = execute_and_evaluate(
        db, game, engine,
        CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
        "variety-2",
    )
    assert second.success and unlocks == ()

    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="workshop_yard")).success
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_round_1")).success
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
    third, unlocks = execute_and_evaluate(
        db, game, engine,
        CanonicalAction(player, ActionType.THROW, item_id="stone_round_1", target_id="tavern_sign"),
        "variety-3",
    )
    assert third.success
    assert [(u.kind, u.code) for u in unlocks] == [
        ("achievement", "THROWING_HABIT_1"),
        ("ability", "STEADY_HAND"),
    ]

    with db.connect() as conn:
        achievement = conn.execute(
            "SELECT trigger_event_id, evidence_json FROM player_achievements WHERE player_actor_id=? AND achievement_code='THROWING_HABIT_1'",
            (player,),
        ).fetchone()
        evidence = json.loads(achievement["evidence_json"])
        assert achievement["trigger_event_id"] == third.event_id
        assert evidence["successful_throw_count"] == 3
        assert evidence["projectile_ids"] == ["stone_flat_1", "stone_round_1"]
        conn.execute("BEGIN IMMEDIATE")
        assert engine.evaluate_after_event(conn, player, third.event_id, "2026-08-14T08:11:00+00:00") == ()
        conn.commit()
        assert conn.execute("SELECT COUNT(*) FROM player_achievements").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM player_abilities").fetchone()[0] == 1


def test_failed_throw_events_never_count_toward_progression(tmp_path):
    db, game = make_game(tmp_path)
    engine = ProgressionEngine()
    player = game.register_player("discord-fail-progress", "Failer")
    for index in range(4):
        result, unlocks = execute_and_evaluate(
            db,
            game,
            engine,
            CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="workbench"),
            f"failed-throw-{index}",
        )
        assert result.success is False
        assert unlocks == ()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM player_achievements").fetchone()[0] == 0


def perform_three_throw_variety(game, player, *, third_external_id="integrated-third"):
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
    assert game.execute(
        CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
        external_id="integrated-first",
    ).success
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    assert game.execute(
        CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
        external_id="integrated-second",
    ).success
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="workshop_yard")).success
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_round_1")).success
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
    return game.execute(
        CanonicalAction(player, ActionType.THROW, item_id="stone_round_1", target_id="tavern_sign"),
        external_id=third_external_id,
    )


def test_game_service_atomically_returns_and_replays_progression_unlocks(tmp_path):
    db, game = make_game(tmp_path, with_progression=True)
    player = game.register_player("discord-integrated-progress", "Thrower")
    third = perform_three_throw_variety(game, player)
    assert third.data["unlocks"] == [
        {"kind": "achievement", "code": "THROWING_HABIT_1", "name": "Рука помнит дугу"},
        {"kind": "ability", "code": "STEADY_HAND", "name": "Твёрдая рука"},
    ]
    replay = game.execute(
        CanonicalAction(player, ActionType.THROW, item_id="stone_round_1", target_id="tavern_sign"),
        external_id="integrated-third",
    )
    assert replay.replayed is True
    assert replay.event_id == third.event_id
    assert replay.data["unlocks"] == third.data["unlocks"]
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM player_achievements").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM player_abilities").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM action_events WHERE action_type='THROW' AND success=1").fetchone()[0] == 3


def test_steady_hand_applies_plus_five_only_after_unlock_and_survives_restart(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    path = tmp_path / "game.db"
    db = GameDatabase(path)
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    player = game.register_player("discord-ability", "Thrower")
    trigger = perform_three_throw_variety(game, player, third_external_id="ability-trigger")
    assert trigger.data["damage"] == 20
    assert trigger.data["base_damage"] == 20
    assert trigger.data["ability_bonus"] == 0
    assert trigger.data["condition_after"] == 40

    reopened = GameDatabase(path)
    reopened.initialize()
    restarted = GameService(reopened, FakeClock(now))
    assert restarted.execute(
        CanonicalAction(player, ActionType.TAKE, target_id="stone_round_1"),
        external_id="ability-retake",
    ).success
    boosted = restarted.execute(
        CanonicalAction(player, ActionType.THROW, item_id="stone_round_1", target_id="tavern_sign"),
        external_id="ability-boosted-throw",
    )
    assert boosted.data["base_damage"] == 20
    assert boosted.data["ability_bonus"] == 5
    assert boosted.data["damage"] == 25
    assert boosted.data["condition_before"] == 40
    assert boosted.data["condition_after"] == 15


def test_progression_is_visible_in_world_view_me_and_unlock_response(tmp_path):
    from samseberpg.discord_app import DiscordGameApplication
    from samseberpg.presentation import render_action_result

    _, game = make_game(tmp_path, with_progression=True)
    player = game.register_player("discord-visible-progress", "Thrower")
    trigger = perform_three_throw_variety(game, player, third_external_id="visible-trigger")
    view = game.observe(player)
    assert view.achievement_codes == ("THROWING_HABIT_1",)
    assert view.ability_codes == ("STEADY_HAND",)

    app = DiscordGameApplication(game)
    me_text = app.handle_me("discord-visible-progress", "Thrower")
    assert "Рука помнит дугу" in me_text
    assert "Твёрдая рука" in me_text
    result_text = render_action_result(trigger)
    assert "🏆 Открыто достижение: Рука помнит дугу" in result_text
    assert "✨ Новый навык: Твёрдая рука" in result_text
