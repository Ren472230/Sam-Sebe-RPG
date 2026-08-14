from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.game import GameService


def make_service(tmp_path: Path) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    return db, GameService(db, clock)


def test_two_discord_users_register_as_distinct_players_in_one_world(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    player_a = game.register_player("discord-a", "Ari")
    player_b = game.register_player("discord-b", "Bela")
    assert player_a != player_b
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT actors.id, actors.world_id, players.discord_user_id "
            "FROM players JOIN actors ON actors.id = players.actor_id "
            "ORDER BY players.discord_user_id"
        ).fetchall()
    assert [(row[1], row[2]) for row in rows] == [
        ("village_1", "discord-a"),
        ("village_1", "discord-b"),
    ]


def test_registration_is_idempotent_for_same_discord_user(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    first = game.register_player("discord-a", "Ari")
    second = game.register_player("discord-a", "Changed Name")
    assert second == first
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM players WHERE discord_user_id = ?", ("discord-a",)).fetchone()[0] == 1
        assert conn.execute("SELECT name FROM actors WHERE id = ?", (first,)).fetchone()[0] == "Ari"


def test_two_players_observe_same_shared_stone_and_each_other(tmp_path: Path) -> None:
    _, game = make_service(tmp_path)
    player_a = game.register_player("discord-a", "Ari")
    player_b = game.register_player("discord-b", "Bela")
    view_a = game.observe(player_a)
    view_b = game.observe(player_b)
    assert view_a.location_id == "workshop_yard"
    assert view_b.location_id == "workshop_yard"
    assert "stone_flat_1" in {entity.entity_id for entity in view_a.visible_entities}
    assert "stone_flat_1" in {entity.entity_id for entity in view_b.visible_entities}
    assert player_b in {actor.actor_id for actor in view_a.visible_actors}
    assert player_a in {actor.actor_id for actor in view_b.visible_actors}
    assert player_a not in {actor.actor_id for actor in view_a.visible_actors}
    assert player_b not in {actor.actor_id for actor in view_b.visible_actors}
    assert view_a.inventory == ()
    assert view_b.inventory == ()


from samseberpg.domain import ActionType, CanonicalAction


def test_move_succeeds_only_to_adjacent_location_and_records_events(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    player = game.register_player("discord-a", "Ari")
    moved = game.execute(CanonicalAction(actor_id=player, action_type=ActionType.MOVE, destination_id="village_square"))
    invalid = game.execute(CanonicalAction(actor_id=player, action_type=ActionType.MOVE, destination_id="missing_location"))
    assert moved.success is True
    assert moved.code == "OK"
    assert game.observe(player).location_id == "village_square"
    assert invalid.success is False
    assert invalid.code == "INVALID_DESTINATION"
    with db.connect() as conn:
        rows = conn.execute("SELECT success, result_code FROM action_events WHERE actor_id = ? ORDER BY id", (player,)).fetchall()
    assert [(row[0], row[1]) for row in rows] == [(1, "OK"), (0, "INVALID_DESTINATION")]


def test_take_changes_shared_world_and_drop_returns_item(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    player_a = game.register_player("discord-a", "Ari")
    player_b = game.register_player("discord-b", "Bela")
    taken = game.execute(CanonicalAction(actor_id=player_a, action_type=ActionType.TAKE, target_id="stone_flat_1"))
    assert taken.success is True
    assert taken.code == "OK"
    assert "stone_flat_1" in {item.entity_id for item in game.observe(player_a).inventory}
    assert "stone_flat_1" not in {item.entity_id for item in game.observe(player_b).visible_entities}
    with db.connect() as conn:
        stone = conn.execute("SELECT location_id, owner_actor_id FROM entities WHERE id = 'stone_flat_1'").fetchone()
    assert tuple(stone) == (None, player_a)
    dropped = game.execute(CanonicalAction(actor_id=player_a, action_type=ActionType.DROP, target_id="stone_flat_1"))
    assert dropped.success is True
    assert "stone_flat_1" not in {item.entity_id for item in game.observe(player_a).inventory}
    assert "stone_flat_1" in {item.entity_id for item in game.observe(player_b).visible_entities}


def test_take_and_drop_gameplay_failures_are_typed_and_recorded(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    player_a = game.register_player("discord-a", "Ari")
    player_b = game.register_player("discord-b", "Bela")
    missing = game.execute(CanonicalAction(actor_id=player_a, action_type=ActionType.TAKE, target_id="missing"))
    nonportable = game.execute(CanonicalAction(actor_id=player_a, action_type=ActionType.TAKE, target_id="anvil_1"))
    assert game.execute(CanonicalAction(actor_id=player_a, action_type=ActionType.TAKE, target_id="stone_flat_1")).success
    owned = game.execute(CanonicalAction(actor_id=player_b, action_type=ActionType.TAKE, target_id="stone_flat_1"))
    not_owned = game.execute(CanonicalAction(actor_id=player_b, action_type=ActionType.DROP, target_id="stone_flat_1"))
    player_b_move = game.execute(CanonicalAction(actor_id=player_b, action_type=ActionType.MOVE, destination_id="village_square"))
    assert player_b_move.success
    absent = game.execute(CanonicalAction(actor_id=player_b, action_type=ActionType.TAKE, target_id="smooth_pebble_1"))
    assert [missing.code, nonportable.code, owned.code, not_owned.code, absent.code] == [
        "TARGET_NOT_FOUND", "NOT_PORTABLE", "ALREADY_OWNED", "ITEM_NOT_OWNED", "TARGET_NOT_PRESENT"
    ]
    assert all(not result.success for result in [missing, nonportable, owned, not_owned, absent])
    with db.connect() as conn:
        failures = conn.execute("SELECT COUNT(*) FROM action_events WHERE success = 0").fetchone()[0]
    assert failures == 5


def test_missing_player_returns_typed_failure_event(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    result = game.execute(CanonicalAction(actor_id="player_missing", action_type=ActionType.LOOK))
    assert result.success is False
    assert result.code == "PLAYER_NOT_FOUND"
    with db.connect() as conn:
        event = conn.execute("SELECT actor_id, action_type, success, result_code FROM action_events").fetchone()
    assert tuple(event) == (None, "LOOK", 0, "PLAYER_NOT_FOUND")


def test_look_action_records_success_without_mutating_player_location(tmp_path: Path) -> None:
    db, game = make_service(tmp_path)
    player = game.register_player("discord-a", "Ari")
    result = game.execute(CanonicalAction(actor_id=player, action_type=ActionType.LOOK))
    assert result.success is True
    assert result.code == "OK"
    assert game.observe(player).location_id == "workshop_yard"
    with db.connect() as conn:
        event = conn.execute("SELECT action_type, success, result_code FROM action_events WHERE id = ?", (result.event_id,)).fetchone()
    assert tuple(event) == ("LOOK", 1, "OK")
