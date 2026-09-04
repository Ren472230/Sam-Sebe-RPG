from __future__ import annotations

import json
from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.social_world import SocialWorldService


EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def _game(tmp_path, key: str):
    db = GameDatabase(tmp_path / f"{key}.sqlite3")
    db.initialize()
    game = GameService(
        db,
        FakeClock(EVENING),
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    return db, game, game.register_player(key, "Stream Player")


def _move(game: GameService, player_id: str, destination_id: str):
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.MOVE,
            destination_id=destination_id,
        )
    )
    assert result.success is True


def _take_bread(game: GameService, player_id: str):
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="bread_loaf_1",
        )
    )
    assert result.success is True


def _give_bread(game: GameService, player_id: str):
    return game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="bread_loaf_1",
            recipient_id="npc_oren",
        )
    )


def test_player_can_take_square_bread_and_give_it_to_oren_after_arrival(tmp_path):
    db, game, player_id = _game(tmp_path, "hospitality-after")

    waited = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 10},
        ),
        external_id="hospitality-wait-10",
    )
    assert waited.success is True

    _move(game, player_id, "village_square")
    _take_bread(game, player_id)
    _move(game, player_id, "tavern_interior")

    given = _give_bread(game, player_id)
    assert given.success is True
    assert given.code == "OK"

    conn = db.connect()
    try:
        state = json.loads(
            str(
                conn.execute(
                    "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_oren'"
                ).fetchone()[0]
            )
        )
        assert state == {"bread_received": True, "bread_requested": False}
        bread = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'bread_loaf_1'"
        ).fetchone()
        assert bread[0] is None
        assert bread[1] is None
    finally:
        conn.close()


def test_oren_rejects_bread_before_wayfarer_arrival_without_consuming_it(tmp_path):
    db, game, player_id = _game(tmp_path, "hospitality-before")

    _move(game, player_id, "village_square")
    _take_bread(game, player_id)
    _move(game, player_id, "tavern_interior")

    given = _give_bread(game, player_id)
    assert given.success is False
    assert given.code == "RESOURCE_NOT_NEEDED"

    conn = db.connect()
    try:
        state = json.loads(
            str(
                conn.execute(
                    "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_oren'"
                ).fetchone()[0]
            )
        )
        assert state == {"bread_received": False, "bread_requested": False}
        bread = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'bread_loaf_1'"
        ).fetchone()
        assert bread[0] is None
        assert bread[1] == player_id
    finally:
        conn.close()
