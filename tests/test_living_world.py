from pathlib import Path

from samseberpg.db import GameDatabase


def make_db(tmp_path: Path) -> GameDatabase:
    db = GameDatabase(tmp_path / "living.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db


def test_living_world_bootstrap_has_persistent_npc_state_and_event_table(tmp_path: Path) -> None:
    db = make_db(tmp_path)

    assert "world_events" in db.list_tables()
    mira = db.fetch_entity("mira_craftswoman")
    kaspar = db.fetch_entity("kaspar_forager")
    driftwood = db.fetch_entity("driftwood_1")

    assert mira is not None
    assert mira["state"]["wood_stock"] == 2
    assert mira["state"]["work_cycles"] == 0
    assert mira["state"]["requested_wood"] is False
    assert kaspar is not None
    assert kaspar["state"]["carrying_wood"] == 0
    assert driftwood is not None
    assert "useful_wood" in driftwood["tags"]
    assert db.list_world_events() == []


def test_mira_works_on_even_ticks_then_requests_wood_once(tmp_path: Path) -> None:
    from samseberpg.living_world import LivingWorldService

    db = make_db(tmp_path)
    living = LivingWorldService()
    with db.connect() as conn:
        living.tick(conn, 2)
        living.tick(conn, 4)
        living.tick(conn, 5)
        living.tick(conn, 6)

    mira = db.fetch_entity("mira_craftswoman")
    assert mira is not None
    assert mira["state"]["wood_stock"] == 0
    assert mira["state"]["work_cycles"] == 2
    assert mira["state"]["requested_wood"] is True
    mira_events = [
        event["event_type"]
        for event in db.list_world_events()
        if event["actor_id"] == "mira_craftswoman"
    ]
    assert mira_events == [
        "NPC_WORKED",
        "NPC_WORKED",
        "NPC_REQUESTED_RESOURCE",
    ]


def test_kaspar_answers_request_collects_returns_and_delivers(tmp_path: Path) -> None:
    from samseberpg.living_world import LivingWorldService

    db = make_db(tmp_path)
    living = LivingWorldService()
    with db.connect() as conn:
        for tick in range(1, 9):
            living.tick(conn, tick)

    mira = db.fetch_entity("mira_craftswoman")
    kaspar = db.fetch_entity("kaspar_forager")
    driftwood = db.fetch_entity("driftwood_1")
    assert mira is not None and kaspar is not None and driftwood is not None
    assert mira["state"]["wood_stock"] == 1
    assert mira["state"]["requested_wood"] is False
    assert kaspar["state"]["carrying_wood"] == 0
    assert kaspar["location_id"] == "workshop_yard"
    assert driftwood["location_id"] is None

    events = db.list_world_events()
    assert [event["event_type"] for event in events] == [
        "NPC_WORKED",
        "NPC_WORKED",
        "NPC_REQUESTED_RESOURCE",
        "NPC_COLLECTED_RESOURCE",
        "NPC_MOVED",
        "NPC_MOVED",
        "NPC_DELIVERED_RESOURCE",
    ]
    collected = next(event for event in events if event["event_type"] == "NPC_COLLECTED_RESOURCE")
    delivered = next(event for event in events if event["event_type"] == "NPC_DELIVERED_RESOURCE")
    assert collected["actor_id"] == "kaspar_forager"
    assert collected["target_id"] == "driftwood_1"
    assert delivered["target_id"] == "mira_craftswoman"
    assert delivered["data"]["resource_id"] == "driftwood_1"


def make_game(tmp_path: Path, name: str):
    from samseberpg.game import GameService

    db = GameDatabase(tmp_path / name)
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=1)


def _autonomous_snapshot(db: GameDatabase) -> dict[str, object]:
    mira = db.fetch_entity("mira_craftswoman")
    kaspar = db.fetch_entity("kaspar_forager")
    driftwood = db.fetch_entity("driftwood_1")
    assert mira is not None and kaspar is not None and driftwood is not None
    return {
        "mira_state": mira["state"],
        "mira_location": mira["location_id"],
        "kaspar_state": kaspar["state"],
        "kaspar_location": kaspar["location_id"],
        "driftwood_location": driftwood["location_id"],
        "event_types": [event["event_type"] for event in db.list_world_events()],
    }


def test_wait_many_matches_repeated_single_ticks(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db_many, game_many = make_game(tmp_path, "many.db")
    db_single, game_single = make_game(tmp_path, "single.db")

    result = game_many.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 9})
    )
    assert result.success
    for _ in range(9):
        result = game_single.execute(
            CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 1})
        )
        assert result.success

    many = _autonomous_snapshot(db_many)
    single = _autonomous_snapshot(db_single)
    assert "NPC_DELIVERED_RESOURCE" in many["event_types"]
    assert many == single


def test_player_taking_driftwood_blocks_kaspar_collection(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = make_game(tmp_path, "block.db")
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="river_edge")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="driftwood_1")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 8})
    ).success

    event_types = [event["event_type"] for event in db.list_world_events()]
    assert "NPC_REQUESTED_RESOURCE" in event_types
    assert "NPC_COLLECTED_RESOURCE" not in event_types
    assert "NPC_DELIVERED_RESOURCE" not in event_types
    assert "driftwood_1" in db.list_inventory("player_1")
    mira = db.fetch_entity("mira_craftswoman")
    assert mira is not None
    assert mira["state"]["requested_wood"] is True


def test_player_giving_driftwood_satisfies_same_mira_wood_need(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = make_game(tmp_path, "satisfy.db")
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="river_edge")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="driftwood_1")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="workshop_yard")
    ).success

    before = db.fetch_entity("mira_craftswoman")
    assert before is not None
    assert before["state"]["wood_stock"] == 0
    assert before["state"]["requested_wood"] is True

    result = game.execute(
        CanonicalAction(
            "player_1",
            ActionType.GIVE,
            target_id="mira_craftswoman",
            item_id="driftwood_1",
        )
    )
    assert result.success

    after = db.fetch_entity("mira_craftswoman")
    assert after is not None
    assert after["state"]["wood_stock"] == 0
    assert after["state"]["work_cycles"] == 3
    assert after["state"]["requested_wood"] is False
    assert not any(
        event["event_type"] == "NPC_DELIVERED_RESOURCE"
        for event in db.list_world_events()
    )


def test_bootstrap_merges_living_world_defaults_into_existing_npc_state(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    with db.connect() as conn:
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE entity_id = 'mira_craftswoman'",
            ('{"received_contributions":["flat_stone"]}',),
        )
        conn.execute(
            "UPDATE entities SET state_json = '{}' WHERE entity_id = 'kaspar_forager'"
        )

    db.bootstrap_if_empty()

    mira = db.fetch_entity("mira_craftswoman")
    kaspar = db.fetch_entity("kaspar_forager")
    assert mira is not None and kaspar is not None
    assert mira["state"]["received_contributions"] == ["flat_stone"]
    assert mira["state"]["wood_stock"] == 2
    assert mira["state"]["work_cycles"] == 0
    assert mira["state"]["requested_wood"] is False
    assert kaspar["state"]["carrying_wood"] == 0


def test_autonomous_chain_continues_after_database_reopen(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction
    from samseberpg.game import GameService

    db, game = make_game(tmp_path, "reopen.db")
    assert game.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 7})
    ).success

    kaspar_before = db.fetch_entity("kaspar_forager")
    assert kaspar_before is not None
    assert kaspar_before["location_id"] == "workshop_yard"
    assert kaspar_before["state"]["carrying_wood"] == 1

    reopened = GameDatabase(db.path)
    game_after_reopen = GameService(reopened, seed=999)
    assert game_after_reopen.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 1})
    ).success

    mira_after = reopened.fetch_entity("mira_craftswoman")
    kaspar_after = reopened.fetch_entity("kaspar_forager")
    assert mira_after is not None and kaspar_after is not None
    assert mira_after["state"]["wood_stock"] == 1
    assert mira_after["state"]["requested_wood"] is False
    assert kaspar_after["state"]["carrying_wood"] == 0
    assert reopened.list_world_events()[-1]["event_type"] == "NPC_DELIVERED_RESOURCE"


def test_talk_exposes_mira_waiting_state_without_internal_goal_ids(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction

    db, game = make_game(tmp_path, "talk-state.db")
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="river_edge")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.TAKE, item_id="driftwood_1")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")
    ).success
    assert game.execute(
        CanonicalAction("player_1", ActionType.MOVE, destination_id="workshop_yard")
    ).success

    result = game.execute(
        CanonicalAction("player_1", ActionType.TALK, target_id="mira_craftswoman")
    )
    assert result.success
    text = result.summary.lower()
    assert "жд" in text
    assert "древес" in text or "материал" in text
    assert "request_wood" not in text
    assert "wait_for_wood" not in text


def test_report_keeps_world_events_separate_from_player_action_counts(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction
    from samseberpg.reporting import build_playtest_report

    db, game = make_game(tmp_path, "report-world.db")
    assert game.execute(
        CanonicalAction("player_1", ActionType.WAIT, modifiers={"ticks": 9})
    ).success

    report = build_playtest_report(db)
    assert report["action_counts"] == {"WAIT": 1}
    assert report["world_events_total"] == len(db.list_world_events())
    assert report["world_event_counts"]["NPC_DELIVERED_RESOURCE"] == 1
    assert 1 <= len(report["latest_world_events"]) <= 10
    assert all("event_type" in event for event in report["latest_world_events"])
