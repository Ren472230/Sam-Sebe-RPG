from __future__ import annotations

from datetime import datetime, timezone

import samseberpg.game as game_module
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import (
    ActionType,
    CanonicalAction,
    MechanicPrimitive,
    MechanicSpec,
)
from samseberpg.game import GameService
from samseberpg.progression import AIMED_THROW_SPEC, MechanicValidator


def test_valid_aimed_throw_accuracy_bonus_is_accepted() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        mechanic_id="aimed_throw",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=0.10,
    )

    assert validator.validate(spec) == (True, "OK")
    assert validator.validate(AIMED_THROW_SPEC) == (True, "OK")


def test_out_of_range_accuracy_bonus_is_rejected() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        mechanic_id="god_throw",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=1.00,
    )

    assert validator.validate(spec) == (False, "LIMIT_EXCEEDED")


def test_unknown_primitive_is_rejected_without_dynamic_execution() -> None:
    validator = MechanicValidator()
    spec = MechanicSpec(
        mechanic_id="unsafe",
        primitive="EXECUTE_CODE",
        magnitude=0.01,
    )

    assert validator.validate(spec) == (False, "UNKNOWN_PRIMITIVE")


def test_numeric_modifier_requires_a_non_negative_number() -> None:
    validator = MechanicValidator()

    invalid_type = MechanicSpec(
        mechanic_id="bad_type",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude="ten percent",
    )
    negative = MechanicSpec(
        mechanic_id="negative",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=-0.10,
    )

    assert validator.validate(invalid_type) == (False, "INVALID_MAGNITUDE")
    assert validator.validate(negative) == (False, "INVALID_MAGNITUDE")


def test_runtime_rejects_a_tampered_unbounded_mechanic_spec(tmp_path, monkeypatch) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    game = GameService(db, clock, seed=9)
    player = game.register_player("discord-a", "Ari")
    assert game.execute(
        CanonicalAction(actor_id=player, action_type=ActionType.TAKE, target_id="stone_flat_1")
    ).success

    with db.connect() as conn:
        conn.execute(
            "INSERT INTO abilities (actor_id, ability_id, source_achievement_id, unlocked_at) "
            "VALUES (?, 'aimed_throw', 'test_fixture', '2026-08-14T08:00:00.000Z')",
            (player,),
        )

    unsafe_spec = MechanicSpec(
        mechanic_id="aimed_throw",
        primitive=MechanicPrimitive.MODIFY_ACCURACY,
        magnitude=1.00,
    )
    monkeypatch.setattr(game_module, "AIMED_THROW_SPEC", unsafe_spec, raising=False)

    result = game.execute(
        CanonicalAction(
            actor_id=player,
            action_type=ActionType.THROW,
            target_id="npc_mira",
            item_id="stone_flat_1",
            modifiers={"aimed": True},
        )
    )

    assert result.success is False
    assert result.code == "MECHANIC_INVALID"
    with db.connect() as conn:
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()[0]
    assert owner == player
