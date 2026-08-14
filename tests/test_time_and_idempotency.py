from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(path, now):
    db = GameDatabase(path)
    db.initialize()
    db.bootstrap_if_empty(now)
    return db, GameService(db, FakeClock(now))


def test_duplicate_external_id_replays_original_result_without_second_event(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db, game = make_game(tmp_path / "game.db", now)
    player = game.register_player("discord-a", "Ren")
    action = CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")
    first = game.execute(action, external_id="discord-123")
    second = game.execute(action, external_id="discord-123")
    assert first.success is True
    assert second.success is True
    assert second.code == first.code
    assert second.event_id == first.event_id
    assert second.replayed is True
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()[0]
        assert owner == player


def test_restart_preserves_item_ownership_and_event_history(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    path = tmp_path / "game.db"
    db, game = make_game(path, now)
    player = game.register_player("discord-a", "Ren")
    result = game.execute(
        CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1"),
        external_id="take-persist",
    )
    assert result.success is True
    reopened = GameDatabase(path)
    reopened.initialize()
    game2 = GameService(reopened, FakeClock(now))
    assert "stone_flat_1" in {e.id for e in game2.observe(player).inventory}
    with reopened.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1


def test_observation_lazily_catches_npc_schedule_up_to_fake_clock(tmp_path):
    morning = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    evening = datetime(2026, 8, 14, 20, 0, tzinfo=timezone.utc)
    path = tmp_path / "game.db"
    db = GameDatabase(path)
    db.initialize()
    db.bootstrap_if_empty(morning)
    clock = FakeClock(morning)
    game = GameService(db, clock)
    player = game.register_player("discord-a", "Ren")
    morning_view = game.observe(player)
    assert "npc_mira" in {actor.id for actor in morning_view.actors}
    clock.set(evening)
    game.observe(player)
    with db.connect() as conn:
        mira = conn.execute(
            """
            SELECT a.location_id, n.current_activity
            FROM actors a JOIN npcs n ON n.actor_id = a.id
            WHERE a.id = 'npc_mira'
            """
        ).fetchone()
        assert mira["location_id"] == "village_square"
        assert mira["current_activity"] == "ужинает и разговаривает в таверне"
        last = conn.execute(
            "SELECT last_simulated_at FROM worlds WHERE id = 'village_1'"
        ).fetchone()[0]
        assert last == evening.isoformat()
