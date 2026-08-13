from collections import Counter
from pathlib import Path

import pytest

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, name: str):
    db = GameDatabase(tmp_path / name)
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=1)


def assert_no_world_inventory_duplication(db: GameDatabase) -> None:
    with db.connect() as conn:
        rows = conn.execute(
            """
            SELECT e.entity_id, e.location_id,
                   EXISTS(SELECT 1 FROM inventory i WHERE i.item_id=e.entity_id) AS owned
            FROM entities e
            WHERE e.entity_type='item'
            """
        ).fetchall()
    for row in rows:
        assert not (row["location_id"] is not None and bool(row["owned"])), row["entity_id"]


@pytest.mark.parametrize("ticks", [1, 2, 5, 9, 12])
def test_wait_many_matches_repeated_single_ticks_for_world_state(tmp_path: Path, ticks: int) -> None:
    db_many, game_many = make_game(tmp_path, f"many-{ticks}.db")
    db_single, game_single = make_game(tmp_path, f"single-{ticks}.db")

    assert game_many.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": ticks})
    ).success
    for _ in range(ticks):
        assert game_single.execute(
            CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 1})
        ).success

    for entity_id in ("mira_craftswoman", "kaspar_forager", "driftwood_1"):
        assert db_many.fetch_entity(entity_id) == db_single.fetch_entity(entity_id)
    assert db_many.get_world_time() == db_single.get_world_time() == ticks
    assert [e["event_type"] for e in db_many.list_world_events()] == [
        e["event_type"] for e in db_single.list_world_events()
    ]


def test_living_world_actor_performs_at_most_one_autonomous_action_per_tick(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, "one-action.db")
    assert game.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 20})
    ).success

    counts = Counter(
        (event["world_time"], event["actor_id"])
        for event in db.list_world_events()
    )
    assert max(counts.values(), default=0) <= 1


def test_touched_item_flows_never_duplicate_world_and_inventory_state(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, "items.db")
    assert_no_world_inventory_duplication(db)

    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success
    assert_no_world_inventory_duplication(db)

    assert game.execute(
        CanonicalAction("player_1", ActionType.DROP, item_id="stone_flat_1")
    ).success
    assert_no_world_inventory_duplication(db)

    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success
    assert game.execute(
        CanonicalAction(
            "player_1", ActionType.GIVE,
            target_id="mira_craftswoman", item_id="stone_flat_1",
        )
    ).success
    assert_no_world_inventory_duplication(db)


def test_action_event_resolution_ticks_are_monotonic(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, "monotonic.db")
    actions = [
        CanonicalAction("player_1", ActionType.LOOK),
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1"),
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 3}),
        CanonicalAction("player_1", ActionType.DROP, item_id="stone_flat_1"),
    ]
    for action in actions:
        game.execute(action)

    events = db.list_events("player_1")
    resolved = [event["resolved_at_tick"] for event in events]
    assert resolved == sorted(resolved)
    assert all(event["world_time"] == event["resolved_at_tick"] for event in events)
