from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, *, seed: int = 1) -> tuple[GameDatabase, GameService]:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    return db, GameService(db, clock, seed=seed)


def test_throw_moves_owned_projectile_to_world_and_records_behavior_evidence(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ari")
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success

    result = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.THROW,
            target_id="npc_mira",
            item_id="stone_flat_1",
        )
    )

    assert result.success is True
    assert result.code == "OK"
    with db.connect() as conn:
        stone = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()
        event = conn.execute(
            "SELECT action_type, target_id, location_id, success, evidence_json "
            "FROM action_events WHERE id = ?",
            (result.event_id,),
        ).fetchone()

    assert tuple(stone) == ("workshop_yard", None)
    assert tuple(event[:4]) == ("THROW", "npc_mira", "workshop_yard", 1)
    evidence = json.loads(event[4])
    assert evidence["item_id"] == "stone_flat_1"
    assert evidence["projectile_type"] == "flat_stone"
    assert evidence["hit"] in (True, False)
    assert 0.0 <= evidence["accuracy_roll"] < 1.0


def test_throw_rejects_unknown_or_malformed_modifiers_without_mutation(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ari")
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success

    for modifiers in ({"aimed": "yes"}, {"god_mode": True}):
        result = game.execute(
            CanonicalAction(
                actor_id=player,
                action_type=ActionType.THROW,
                target_id="npc_mira",
                item_id="stone_flat_1",
                modifiers=modifiers,
            )
        )

        assert result.success is False
        assert result.code == "INVALID_MODIFIER"
        with db.connect() as conn:
            owner = conn.execute(
                "SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
            ).fetchone()[0]
            event = conn.execute(
                "SELECT success, result_code FROM action_events WHERE id = ?",
                (result.event_id,),
            ).fetchone()
        assert owner == player
        assert tuple(event) == (0, "INVALID_MODIFIER")


def test_throw_rng_sequence_does_not_reset_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "world.sqlite3"
    db = GameDatabase(db_path)
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    game = GameService(db, clock, seed=9)
    player = game.register_player("discord-a", "Ari")
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success

    first = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.THROW,
            target_id="npc_mira",
            item_id="stone_flat_1",
        )
    )
    assert first.success
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success

    reopened_db = GameDatabase(db_path)
    reopened_db.initialize()
    reopened_game = GameService(reopened_db, clock, seed=9)
    second = reopened_game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.THROW,
            target_id="npc_mira",
            item_id="stone_flat_1",
        )
    )
    assert second.success

    with reopened_db.connect() as conn:
        rolls = [
            json.loads(row[0])["accuracy_roll"]
            for row in conn.execute(
                "SELECT evidence_json FROM action_events "
                "WHERE actor_id = ? AND action_type = 'THROW' AND success = 1 ORDER BY id",
                (player,),
            ).fetchall()
        ]

    assert len(rolls) == 2
    assert rolls[0] != rolls[1]
