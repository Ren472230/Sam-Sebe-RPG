from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path) -> tuple[GameDatabase, GameService, str]:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    game = GameService(db, FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)))
    player = game.register_player("discord-a", "Ari")
    return db, game, player


def test_give_transfers_owned_item_to_visible_npc_atomically(tmp_path: Path) -> None:
    db, game, player = make_game(tmp_path)
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success

    result = game.execute(
        CanonicalAction(player, ActionType.GIVE, item_id="stone_flat_1", target_id="npc_mira")
    )

    assert result.success is True
    assert result.code == "OK"
    assert "stone_flat_1" not in {item.entity_id for item in game.observe(player).inventory}
    with db.connect() as conn:
        row = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()
        event = conn.execute(
            "SELECT action_type, target_id, success, evidence_json FROM action_events WHERE id = ?",
            (result.event_id,),
        ).fetchone()
    assert tuple(row) == (None, "npc_mira")
    assert tuple(event[:3]) == ("GIVE", "npc_mira", 1)
    assert json.loads(event[3])["item_id"] == "stone_flat_1"


def test_give_rejects_unowned_or_nonpresent_target_without_mutation(tmp_path: Path) -> None:
    db, game, player = make_game(tmp_path)
    unowned = game.execute(
        CanonicalAction(player, ActionType.GIVE, item_id="stone_flat_1", target_id="npc_mira")
    )
    assert unowned.success is False
    assert unowned.code == "ITEM_NOT_OWNED"

    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    absent = game.execute(
        CanonicalAction(player, ActionType.GIVE, item_id="stone_flat_1", target_id="npc_oren")
    )
    assert absent.success is False
    assert absent.code == "TARGET_NOT_PRESENT"
    assert "stone_flat_1" in {item.entity_id for item in game.observe(player).inventory}
    with db.connect() as conn:
        owner = conn.execute("SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
    assert owner == player


def test_give_can_transfer_to_another_visible_player(tmp_path: Path) -> None:
    db, game, player = make_game(tmp_path)
    other = game.register_player("discord-b", "Bela")
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success

    result = game.execute(
        CanonicalAction(player, ActionType.GIVE, item_id="stone_flat_1", target_id=other)
    )

    assert result.success is True
    assert "stone_flat_1" in {item.entity_id for item in game.observe(other).inventory}
    with db.connect() as conn:
        owner = conn.execute("SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
    assert owner == other


def test_give_external_id_is_exactly_once_even_after_ownership_changes(tmp_path: Path) -> None:
    db, game, player = make_game(tmp_path)
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    action = CanonicalAction(player, ActionType.GIVE, item_id="stone_flat_1", target_id="npc_mira")

    first = game.execute(action, external_id="discord-message-42")
    replay = game.execute(action, external_id="discord-message-42")

    assert first.success is True
    assert replay.success is True
    assert replay.replayed is True
    assert replay.event_id == first.event_id
    with db.connect() as conn:
        events = conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE external_id = 'discord-message-42'"
        ).fetchone()[0]
        owner = conn.execute("SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
    assert events == 1
    assert owner == "npc_mira"
