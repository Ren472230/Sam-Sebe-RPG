from __future__ import annotations

import json
from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, name: str = "audit.db", seed: int = 4):
    db = GameDatabase(tmp_path / name)
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def trust(db: GameDatabase, npc_id: str) -> float:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT value FROM relations
            WHERE source_id=? AND target_id='player_1' AND relation_type='trust'
            """,
            (npc_id,),
        ).fetchone()
    return float(row["value"]) if row else 0.0


def test_successful_take_event_uses_completion_tick(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success

    event = db.list_events("player_1")[-1]
    assert event["started_at_tick"] == 0
    assert event["resolved_at_tick"] == 1
    assert event["world_time"] == 1
    assert event["duration_ticks"] == 1


def test_wait_three_records_start_resolution_and_duration(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    assert game.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 3})
    ).success

    event = db.list_events("player_1")[-1]
    assert event["started_at_tick"] == 0
    assert event["resolved_at_tick"] == 3
    assert event["world_time"] == 3
    assert event["duration_ticks"] == 3


def test_failed_action_is_zero_duration_and_does_not_advance_world(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    result = game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="pinecone_1")
    )

    assert result.success is False
    assert db.get_world_time() == 0
    event = db.list_events("player_1")[-1]
    assert event["world_time"] == 0
    assert event["started_at_tick"] == 0
    assert event["resolved_at_tick"] == 0
    assert event["duration_ticks"] == 0


def test_same_location_living_world_event_is_attached_to_action_result(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)
    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success

    result = game.execute(
        CanonicalAction("player_1", ActionType.DROP, item_id="stone_flat_1")
    )

    observed = result.data["observed_world_events"]
    assert [event["event_type"] for event in observed] == ["NPC_WORKED"]
    assert all(event["location_id"] == "workshop_yard" for event in observed)


def test_offscreen_living_world_event_is_not_attached(tmp_path: Path) -> None:
    _db, game = make_game(tmp_path)
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success

    result = game.execute(
        CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper")
    )

    observed = result.data["observed_world_events"]
    assert observed == []


def test_two_starter_stones_give_two_coins_and_social_vouch(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    for item_id in ("stone_flat_1", "stone_round_1"):
        assert game.execute(
            CanonicalAction("player_1", ActionType.TAKE, item_id=item_id)
        ).success
        assert game.execute(
            CanonicalAction(
                "player_1", ActionType.GIVE,
                target_id="mira_craftswoman", item_id=item_id,
            )
        ).success

    assert db.fetch_player_resources("player_1")["coins"] == 2
    assert trust(db, "mira_craftswoman") == 2

    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success
    lodging = game.execute(
        CanonicalAction(
            "player_1", ActionType.TALK,
            target_id="oren_innkeeper", modifiers={"topic": "request_lodging"},
        )
    )
    assert lodging.success
    assert db.fetch_player_resources("player_1")["lodging_secured"] is True
    assert db.fetch_player_resources("player_1")["coins"] == 2


def test_hitting_npc_creates_social_consequence_without_combat_system(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=4)
    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success

    result = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW,
            item_id="stone_flat_1", target_id="mira_craftswoman",
        )
    )

    assert result.success and result.data["hit"] is True
    assert trust(db, "mira_craftswoman") == -2
    mira = db.fetch_entity("mira_craftswoman")
    assert mira is not None
    assert mira["state"]["hit_by_player_count"] == 1
    assert result.data["social_effects"]["target_trust_delta"] == -2


def test_hitting_raven_changes_fear_trust_and_location(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=4)
    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success

    result = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW,
            item_id="stone_flat_1", target_id="raven_1",
        )
    )

    assert result.success and result.data["hit"] is True
    raven = db.fetch_entity("raven_1")
    assert raven is not None
    assert raven["state"]["fear"] == 2
    assert raven["state"]["trust"] == -1
    assert raven["location_id"] == "river_edge"
    assert result.data["animal_effects"]["fled_to"] == "river_edge"


def test_aimed_barrel_hit_has_one_shot_positive_systemic_utility(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=4)
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO abilities(player_id, ability_id, mechanic_json, unlocked_at)
            VALUES ('player_1', 'aimed_throw', ?, 0)
            """,
            (
                json.dumps({
                    "primitive": "MODIFY_ACCURACY",
                    "value": 10,
                    "action": "THROW",
                    "variant": "aimed",
                }),
            ),
        )

    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success
    first = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW,
            item_id="stone_flat_1", target_id="target_barrel",
            modifiers={"aimed": True},
        )
    )
    assert first.success and first.data["hit"] is True
    assert first.data["precision_task_completed"] is True
    barrel = db.fetch_entity("target_barrel")
    assert barrel is not None and barrel["state"]["precision_fixed"] is True
    trust_after_first = trust(db, "mira_craftswoman")
    assert trust_after_first == 1

    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")
    ).success
    second = game.execute(
        CanonicalAction(
            "player_1", ActionType.THROW,
            item_id="stone_flat_1", target_id="target_barrel",
            modifiers={"aimed": True},
        )
    )
    assert second.success
    assert second.data["precision_task_completed"] is False
    assert trust(db, "mira_craftswoman") == trust_after_first
