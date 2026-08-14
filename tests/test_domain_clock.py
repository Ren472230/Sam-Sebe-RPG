from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from samseberpg.clock import FakeClock
from samseberpg.domain import ActionResult, ActionType, CanonicalAction


def test_canonical_action_uses_typed_action_enum() -> None:
    action = CanonicalAction(
        actor_id="player_1",
        action_type=ActionType.TAKE,
        target_id="stone_flat_1",
        source_text="take the flat stone",
    )

    assert action.action_type is ActionType.TAKE
    assert action.destination_id is None


def test_action_result_defaults_to_non_replayed() -> None:
    result = ActionResult(success=True, code="OK", summary="done")

    assert result.replayed is False


def test_fake_clock_is_timezone_aware_and_advanceable() -> None:
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))

    clock.advance(timedelta(hours=12))

    assert clock.now() == datetime(2026, 8, 14, 20, 0, tzinfo=timezone.utc)


def test_fake_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        FakeClock(datetime(2026, 8, 14, 8, 0))


def test_world_view_has_typed_visible_actor_entity_collections() -> None:
    import samseberpg.domain as domain

    actor = domain.VisibleActor(actor_id="npc_mira", name="Mira", actor_type="npc")
    stone = domain.VisibleEntity(
        entity_id="stone_flat_1",
        name="Flat Stone",
        entity_type="stone",
        portable=True,
    )
    view = domain.WorldView(
        player_id="player_1",
        location_id="workshop_yard",
        location_name="Workshop Yard",
        location_description="A yard.",
        visible_actors=(actor,),
        visible_entities=(stone,),
    )

    assert view.visible_actors == (actor,)
    assert view.visible_entities == (stone,)
    assert view.inventory == ()


def test_system_clock_returns_timezone_aware_utc_datetime() -> None:
    import samseberpg.clock as clock_module

    current = clock_module.SystemClock().now()

    assert current.tzinfo is not None
    assert current.utcoffset() == timedelta(0)
