from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.game import GameService
from samseberpg.intent import build_intent_context


def make_game(tmp_path: Path) -> GameService:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    return GameService(db, FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)))


def test_observe_exposes_existing_authoritative_coins_exits_activity_and_entity_state(tmp_path: Path) -> None:
    game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ari")

    view = game.observe(player)

    assert view.coins == 10
    assert view.exits == ("village_square",)
    mira = next(actor for actor in view.visible_actors if actor.actor_id == "npc_mira")
    assert mira.activity == "working at the bench"
    hammer = next(entity for entity in view.visible_entities if entity.entity_id == "hammer_old_1")
    assert hammer.state == {"condition": "worn"}


def test_real_observe_output_builds_a_useful_intent_context(tmp_path: Path) -> None:
    game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ari")

    context = build_intent_context(game.observe(player))

    assert context.coins == 10
    assert context.exits == ("village_square",)
    assert context.visible_npc_ids == frozenset({"npc_mira"})
    assert context.visible_entity_ids >= frozenset({"stone_flat_1", "hammer_old_1", "anvil_1"})
    hammer = next(entity for entity in context.visible_entities if entity["id"] == "hammer_old_1")
    assert hammer["state"] == {"condition": "worn"}
