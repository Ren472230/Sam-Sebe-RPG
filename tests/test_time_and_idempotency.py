from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(db_path: Path) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(db_path)
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    return db, GameService(db, clock)


def test_duplicate_external_id_replays_without_second_mutation_or_event(tmp_path: Path) -> None:
    db, game = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")
    action = CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    first = game.execute(action, external_id="discord-123")
    second = game.execute(action, external_id="discord-123")
    assert first.success is True
    assert first.replayed is False
    assert second.success is True
    assert second.replayed is True
    assert second.event_id == first.event_id
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events WHERE external_id = 'discord-123'").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM processed_interactions WHERE external_id = 'discord-123'").fetchone()[0] == 1
        owner = conn.execute("SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
    assert owner == player


def test_duplicate_throw_external_id_does_not_inflate_progression_evidence(tmp_path: Path) -> None:
    db, game = make_game(tmp_path / "world.sqlite3")
    player = game.register_player("discord-a", "Ari")
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success
    action = CanonicalAction(
        actor_id=player,
        action_type=ActionType.THROW,
        target_id="npc_mira",
        item_id="stone_flat_1",
    )

    first = game.execute(action, external_id="discord-throw-1")
    replay = game.execute(action, external_id="discord-throw-1")

    assert first.success is True
    assert first.replayed is False
    assert replay.success is True
    assert replay.replayed is True
    assert replay.event_id == first.event_id
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events "
            "WHERE actor_id = ? AND action_type = 'THROW' AND success = 1",
            (player,),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM achievements WHERE actor_id = ?", (player,)
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM abilities WHERE actor_id = ?", (player,)
        ).fetchone()[0] == 0


def test_restart_preserves_item_ownership_event_and_replay_record(tmp_path: Path) -> None:
    db_path = tmp_path / "world.sqlite3"
    _, game = make_game(db_path)
    player = game.register_player("discord-a", "Ari")
    first = game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1"),
        external_id="discord-restart-1",
    )
    assert first.success
    reopened_db, reopened_game = make_game(db_path)
    view = reopened_game.observe(player)
    replay = reopened_game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1"),
        external_id="discord-restart-1",
    )
    assert "stone_flat_1" in {item.entity_id for item in view.inventory}
    assert replay.replayed is True
    assert replay.event_id == first.event_id
    with reopened_db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events WHERE external_id = 'discord-restart-1'").fetchone()[0] == 1


def test_observe_lazily_catches_npc_schedule_up_to_fake_clock(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    player = game.register_player("discord-a", "Ari")
    morning = game.observe(player)
    assert "npc_mira" in {actor.actor_id for actor in morning.visible_actors}
    clock.advance(timedelta(hours=12))
    evening = game.observe(player)
    assert "npc_mira" not in {actor.actor_id for actor in evening.visible_actors}
    with db.connect() as conn:
        mira = conn.execute(
            "SELECT actors.location_id, npcs.current_activity FROM actors "
            "JOIN npcs ON npcs.actor_id = actors.id WHERE actors.id = 'npc_mira'"
        ).fetchone()
        last_simulated_at = conn.execute("SELECT last_simulated_at FROM worlds WHERE id = 'village_1'").fetchone()[0]
    assert tuple(mira) == ("village_square", "running evening errands")
    assert last_simulated_at == "2026-08-14T20:00:00.000Z"


def test_midnight_wrapping_schedule_window_is_resolved_directly(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 23, 30, tzinfo=timezone.utc))
    game = GameService(db, clock)
    player = game.register_player("discord-a", "Ari")
    game.observe(player)
    with db.connect() as conn:
        mira = conn.execute(
            "SELECT actors.location_id, npcs.current_activity FROM actors "
            "JOIN npcs ON npcs.actor_id = actors.id WHERE actors.id = 'npc_mira'"
        ).fetchone()
    assert tuple(mira) == ("workshop_yard", "resting near the workshop")
