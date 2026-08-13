from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path: Path, seed: int = 1):
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db, GameService(db, seed=seed)


def test_talk_action_type_exists() -> None:
    assert hasattr(ActionType, "TALK")


def test_talk_requires_npc_in_current_location(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper"))
    assert result.success is False
    assert result.code == "NPC_NOT_PRESENT"


def test_talk_to_mira_returns_context_not_quest_list(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="mira_craftswoman"))
    assert result.success is True
    assert "кам" in result.summary.lower()
    assert "квест" not in result.summary.lower()


def test_social_service_module_exists() -> None:
    import importlib.util
    assert importlib.util.find_spec("samseberpg.social") is not None


def npc_trust(db: GameDatabase, npc_id: str) -> float:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT value FROM relations WHERE source_id=? AND target_id='player_1' AND relation_type='trust'",
            (npc_id,),
        ).fetchone()
    return float(row[0]) if row else 0.0


def test_first_useful_stone_gift_to_mira_gives_trust_and_one_coin(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")).success
    result = game.execute(
        CanonicalAction("player_1", ActionType.GIVE, target_id="mira_craftswoman", item_id="stone_flat_1")
    )
    assert result.success is True
    assert db.fetch_player_resources("player_1")["coins"] == 1
    assert npc_trust(db, "mira_craftswoman") == 1
    assert "stone_flat_1" not in db.list_inventory("player_1")


def test_same_contribution_tag_cannot_be_farmed_for_more_coins_or_trust(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO entities(entity_id, entity_type, name, location_id, tags_json, state_json) VALUES ('stone_flat_2','item','Ещё один плоский камень','workshop_yard','[\"improvised_projectile\",\"flat_stone\"]','{}')"
        )
    for item_id in ("stone_flat_1", "stone_flat_2"):
        assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id=item_id)).success
        assert game.execute(CanonicalAction("player_1", ActionType.GIVE, target_id="mira_craftswoman", item_id=item_id)).success
    assert db.fetch_player_resources("player_1")["coins"] == 1
    assert npc_trust(db, "mira_craftswoman") == 1


def test_feeding_raven_consumes_food_and_increases_persistent_trust(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="bread_1")).success
    result = game.execute(
        CanonicalAction("player_1", ActionType.FEED, target_id="raven_1", item_id="bread_1")
    )
    assert result.success is True
    raven = db.fetch_entity("raven_1")
    assert raven["state"]["trust"] == 1
    assert "bread_1" not in db.list_inventory("player_1")


def set_coins(db: GameDatabase, amount: int) -> None:
    with db.connect() as conn:
        conn.execute("UPDATE player_resources SET coins=? WHERE player_id='player_1'", (amount,))


def ask_oren_for_lodging(game: GameService):
    return game.execute(
        CanonicalAction(
            "player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "lodging"}
        )
    )


def test_two_coins_do_not_secure_lodging(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    set_coins(db, 2)
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "pay_lodging"}))
    assert result.success is True
    resources = db.fetch_player_resources("player_1")
    assert resources == {"coins": 2, "lodging_secured": False}
    assert "3" in result.summary


def test_three_coins_buy_persistent_lodging_and_are_spent(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    set_coins(db, 3)
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "pay_lodging"}))
    assert result.success is True
    assert db.fetch_player_resources("player_1") == {"coins": 0, "lodging_secured": True}
    reopened = GameDatabase(db.path)
    assert reopened.fetch_player_resources("player_1")["lodging_secured"] is True


def test_local_trust_can_secure_lodging_without_spending_coins(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO relations(source_id,target_id,relation_type,value) VALUES ('mira_craftswoman','player_1','trust',2)"
        )
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "request_lodging"}))
    assert result.success is True
    assert db.fetch_player_resources("player_1") == {"coins": 0, "lodging_secured": True}
    assert "поруч" in result.summary.lower() or "довер" in result.summary.lower()


def test_hitting_inn_sign_lowers_oren_trust(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=4)
    assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")).success
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    result = game.execute(
        CanonicalAction("player_1", ActionType.THROW, item_id="stone_flat_1", target_id="target_sign")
    )
    assert result.success and result.data["hit"] is True
    assert npc_trust(db, "oren_innkeeper") == -1
    assert result.data["social_effects"]["oren_trust_delta"] == -1


def test_missing_inn_sign_does_not_lower_oren_trust(tmp_path: Path) -> None:
    db, game = make_game(tmp_path, seed=0)
    assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")).success
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    result = game.execute(
        CanonicalAction("player_1", ActionType.THROW, item_id="stone_flat_1", target_id="target_sign")
    )
    assert result.success and result.data["hit"] is False
    assert npc_trust(db, "oren_innkeeper") == 0


def test_asking_about_lodging_does_not_spend_money_without_player_choice(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    set_coins(db, 3)
    result = ask_oren_for_lodging(game)
    assert result.success is True
    assert db.fetch_player_resources("player_1") == {"coins": 3, "lodging_secured": False}


def test_explicit_pay_lodging_spends_three_coins_and_secures_bed(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    set_coins(db, 3)
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "pay_lodging"}))
    assert result.success is True
    assert db.fetch_player_resources("player_1") == {"coins": 0, "lodging_secured": True}


def test_explicit_request_lodging_uses_local_trust_without_spending_coins(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)
    with db.connect() as conn:
        conn.execute("INSERT INTO relations(source_id,target_id,relation_type,value) VALUES ('mira_craftswoman','player_1','trust',2)")
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    result = game.execute(CanonicalAction("player_1", ActionType.TALK, target_id="oren_innkeeper", modifiers={"topic": "request_lodging"}))
    assert result.success is True
    assert db.fetch_player_resources("player_1") == {"coins": 0, "lodging_secured": True}
    assert "поруч" in result.summary.lower() or "довер" in result.summary.lower()


def test_social_lodging_route_is_reachable_with_two_distinct_starter_contributions(tmp_path: Path) -> None:
    db, game = make_game(tmp_path)

    for item_id in ("stone_flat_1", "stone_round_1"):
        assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id=item_id)).success
        assert game.execute(
            CanonicalAction(
                "player_1",
                ActionType.GIVE,
                target_id="mira_craftswoman",
                item_id=item_id,
            )
        ).success

    assert npc_trust(db, "mira_craftswoman") == 2
    assert db.fetch_player_resources("player_1")["coins"] == 2

    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    result = game.execute(
        CanonicalAction(
            "player_1",
            ActionType.TALK,
            target_id="oren_innkeeper",
            modifiers={"topic": "request_lodging"},
        )
    )
    assert result.success is True
    assert db.fetch_player_resources("player_1") == {"coins": 2, "lodging_secured": True}
