from __future__ import annotations

from datetime import datetime, timezone

import pytest

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService


class RecordingSocialWorld:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []
        self.in_transaction = False

    def process_world_events(self, conn, events):
        self.events = list(events)
        self.in_transaction = bool(conn.in_transaction)
        return []


class FailingSocialWorld:
    def process_world_events(self, conn, events):
        assert conn.in_transaction is True
        assert list(events)
        raise RuntimeError("social processing failed")


def _make_db(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 4, 17, 0, tzinfo=timezone.utc))
    return db, clock


def _snapshot(db: GameDatabase) -> tuple[int, int, int]:
    with db.connect() as conn:
        tick = int(
            conn.execute(
                "SELECT tick FROM world_runtime WHERE world_id = ?",
                (DEFAULT_WORLD_ID,),
            ).fetchone()[0]
        )
        world_events = int(conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0])
        action_events = int(conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0])
    return tick, world_events, action_events


def test_wait_passes_living_world_events_to_social_world_inside_same_transaction(tmp_path):
    db, clock = _make_db(tmp_path)
    social = RecordingSocialWorld()
    game = GameService(
        db,
        clock,
        living_world=LivingWorldService(),
        social_world=social,
    )
    player_id = game.register_player("social-wait-player", "Ren")

    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 2},
        )
    )

    assert result.success is True
    assert social.in_transaction is True
    assert social.events
    assert all(type(event.get("world_event_id")) is int for event in social.events)


def test_social_failure_rolls_back_physical_wait_and_player_event(tmp_path):
    db, clock = _make_db(tmp_path)
    game = GameService(
        db,
        clock,
        living_world=LivingWorldService(),
        social_world=FailingSocialWorld(),
    )
    player_id = game.register_player("social-rollback-player", "Ren")
    before = _snapshot(db)

    with pytest.raises(RuntimeError, match="social processing failed"):
        game.execute(
            CanonicalAction(
                actor_id=player_id,
                action_type=ActionType.WAIT,
                modifiers={"ticks": 2},
            )
        )

    assert _snapshot(db) == before
