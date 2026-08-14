from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    return db, GameService(db, FakeClock(now))


def test_registration_is_idempotent_and_two_players_share_world(tmp_path):
    db, game = make_game(tmp_path)
    player_a = game.register_player("discord-a", "Ren")
    player_a_again = game.register_player("discord-a", "Ren renamed")
    player_b = game.register_player("discord-b", "TestPlayer")
    assert player_a_again == player_a
    assert player_b != player_a

    with db.connect() as conn:
        rows = conn.execute(
            "SELECT discord_user_id, actor_id FROM players ORDER BY discord_user_id"
        ).fetchall()
        assert [(row["discord_user_id"], row["actor_id"]) for row in rows] == [
            ("discord-a", player_a),
            ("discord-b", player_b),
        ]
        worlds = conn.execute(
            "SELECT DISTINCT world_id FROM actors WHERE id IN (?, ?)",
            (player_a, player_b),
        ).fetchall()
        assert [row["world_id"] for row in worlds] == ["village_1"]


def test_two_players_observe_same_initial_entity(tmp_path):
    _, game = make_game(tmp_path)
    player_a = game.register_player("discord-a", "Ren")
    player_b = game.register_player("discord-b", "TestPlayer")
    view_a = game.observe(player_a)
    view_b = game.observe(player_b)
    assert view_a.location_id == "workshop_yard"
    assert view_b.location_id == "workshop_yard"
    assert "stone_flat_1" in {entity.id for entity in view_a.entities}
    assert "stone_flat_1" in {entity.id for entity in view_b.entities}
    assert player_b in {actor.id for actor in view_a.actors}
    assert player_a in {actor.id for actor in view_b.actors}


def test_move_accepts_adjacent_destination_and_logs_event(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    result = game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square"),
        external_id="move-1",
    )
    assert result.success is True
    assert result.code == "OK"
    assert game.observe(player).location_id == "village_square"
    with db.connect() as conn:
        event = conn.execute(
            "SELECT * FROM action_events WHERE id = ?", (result.event_id,)
        ).fetchone()
        assert event["action_type"] == "MOVE"
        assert event["success"] == 1


def test_invalid_move_is_gameplay_failure_and_is_logged(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    result = game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="river_edge"),
        external_id="move-invalid",
    )
    assert result.success is False
    assert result.code == "INVALID_DESTINATION"
    assert game.observe(player).location_id == "workshop_yard"
    with db.connect() as conn:
        event = conn.execute(
            "SELECT * FROM action_events WHERE id = ?", (result.event_id,)
        ).fetchone()
        assert event["success"] == 0
        assert event["result_code"] == "INVALID_DESTINATION"


def test_take_and_drop_are_visible_to_other_player(tmp_path):
    db, game = make_game(tmp_path)
    player_a = game.register_player("discord-a", "Ren")
    player_b = game.register_player("discord-b", "TestPlayer")
    take = game.execute(
        CanonicalAction(player_a, ActionType.TAKE, target_id="stone_flat_1"),
        external_id="take-1",
    )
    assert take.success is True
    assert "stone_flat_1" in {entity.id for entity in game.observe(player_a).inventory}
    assert "stone_flat_1" not in {entity.id for entity in game.observe(player_b).entities}

    competing_take = game.execute(
        CanonicalAction(player_b, ActionType.TAKE, target_id="stone_flat_1"),
        external_id="take-2",
    )
    assert competing_take.success is False
    assert competing_take.code == "ALREADY_OWNED"

    drop = game.execute(
        CanonicalAction(player_a, ActionType.DROP, target_id="stone_flat_1"),
        external_id="drop-1",
    )
    assert drop.success is True
    assert "stone_flat_1" in {entity.id for entity in game.observe(player_b).entities}
    with db.connect() as conn:
        events = conn.execute(
            "SELECT success, result_code FROM action_events ORDER BY id"
        ).fetchall()
        assert [(row["success"], row["result_code"]) for row in events] == [
            (1, "OK"),
            (0, "ALREADY_OWNED"),
            (1, "OK"),
        ]


def test_look_executes_without_mutating_world_and_logs_event(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    result = game.execute(
        CanonicalAction(player, ActionType.LOOK), external_id="look-1"
    )
    assert result.success is True
    assert result.data["location_id"] == "workshop_yard"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1
