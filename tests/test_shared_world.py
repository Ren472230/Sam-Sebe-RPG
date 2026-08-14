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
