from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    return db, GameService(db, FakeClock(now))


def test_world_exposes_player_money_sale_offer_and_seller_balance(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")

    start = game.observe(player)
    assert start.coins == 10
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success
    square = game.observe(player)
    bottle = next(entity for entity in square.entities if entity.id == "bottle_1")
    assert bottle.state == {
        "price": 3,
        "for_sale_by": "npc_oren",
        "fillable": True,
        "filled_with": None,
    }
    well = next(entity for entity in square.entities if entity.id == "village_well")
    assert well.state["water_source"] is True

    with db.connect() as conn:
        oren_coins = conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0]
    assert oren_coins == 20


def test_take_cannot_bypass_sale_offer(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success

    result = game.execute(
        CanonicalAction(player, ActionType.TAKE, target_id="bottle_1")
    )

    assert result.success is False
    assert result.code == "FOR_SALE_ONLY"
    with db.connect() as conn:
        bottle = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'bottle_1'"
        ).fetchone()
        coins = conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0]
    assert tuple(bottle) == ("village_square", None)
    assert coins == 10


def test_buy_transfers_money_and_item_atomically_with_evidence(tmp_path):
    import json

    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.BUY,
            item_id="bottle_1",
            target_id="npc_oren",
        ),
        external_id="buy-bottle-1",
    )

    assert result.success is True
    assert result.code == "OK"
    with db.connect() as conn:
        buyer_coins = conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0]
        seller_coins = conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0]
        bottle = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'bottle_1'"
        ).fetchone()
        evidence = json.loads(
            conn.execute(
                "SELECT evidence_json FROM action_events WHERE id = ?",
                (result.event_id,),
            ).fetchone()[0]
        )

    assert buyer_coins == 7
    assert seller_coins == 23
    assert tuple(bottle) == (None, player)
    assert evidence == {
        "item_id": "bottle_1",
        "seller_id": "npc_oren",
        "price": 3,
        "buyer_coins_before": 10,
        "buyer_coins_after": 7,
        "seller_coins_before": 20,
        "seller_coins_after": 23,
    }


def test_buy_fails_for_wrong_or_absent_seller_without_mutation(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success

    wrong = game.execute(
        CanonicalAction(
            player,
            ActionType.BUY,
            item_id="bottle_1",
            target_id="npc_mira",
        )
    )
    assert wrong.success is False
    assert wrong.code == "WRONG_SELLER"

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE npc_schedule SET location_id = 'river_edge' WHERE npc_actor_id = 'npc_oren'"
        )
        conn.commit()

    absent = game.execute(
        CanonicalAction(
            player,
            ActionType.BUY,
            item_id="bottle_1",
            target_id="npc_oren",
        )
    )
    assert absent.success is False
    assert absent.code == "SELLER_NOT_PRESENT"

    with db.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0] == 10
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 20
        bottle = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'bottle_1'"
        ).fetchone()
    assert tuple(bottle) == ("village_square", None)


def test_buy_fails_when_player_has_insufficient_funds(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE players SET coins = 2 WHERE actor_id = ?", (player,))
        conn.commit()

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.BUY,
            item_id="bottle_1",
            target_id="npc_oren",
        )
    )

    assert result.success is False
    assert result.code == "INSUFFICIENT_FUNDS"
    with db.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0] == 2
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 20
        assert conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'bottle_1'"
        ).fetchone()[0] is None


def test_duplicate_buy_external_id_cannot_charge_twice(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success
    action = CanonicalAction(
        player,
        ActionType.BUY,
        item_id="bottle_1",
        target_id="npc_oren",
    )

    first = game.execute(action, external_id="same-buy")
    second = game.execute(action, external_id="same-buy")

    assert first.success is True
    assert second.success is True
    assert second.replayed is True
    assert second.event_id == first.event_id
    with db.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0] == 7
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 23
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE action_type = 'BUY'"
        ).fetchone()[0] == 1


def buy_bottle(game, player):
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success
    result = game.execute(
        CanonicalAction(
            player,
            ActionType.BUY,
            item_id="bottle_1",
            target_id="npc_oren",
        )
    )
    assert result.success


def test_use_fills_owned_bottle_from_present_water_source_with_evidence(tmp_path):
    import json

    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    buy_bottle(game, player)

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.USE,
            item_id="bottle_1",
            target_id="village_well",
        ),
        external_id="fill-bottle-1",
    )

    assert result.success is True
    assert result.code == "OK"
    with db.connect() as conn:
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM entities WHERE id = 'bottle_1'"
            ).fetchone()[0]
        )
        evidence = json.loads(
            conn.execute(
                "SELECT evidence_json FROM action_events WHERE id = ?",
                (result.event_id,),
            ).fetchone()[0]
        )
    assert state["filled_with"] == "water"
    assert evidence == {
        "item_id": "bottle_1",
        "target_id": "village_well",
        "filled_before": None,
        "filled_after": "water",
    }


def test_use_requires_owned_item_and_supported_present_target(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")

    unowned = game.execute(
        CanonicalAction(
            player,
            ActionType.USE,
            item_id="bottle_1",
            target_id="workbench",
        )
    )
    assert unowned.success is False
    assert unowned.code == "ITEM_NOT_OWNED"

    buy_bottle(game, player)
    unsupported = game.execute(
        CanonicalAction(
            player,
            ActionType.USE,
            item_id="bottle_1",
            target_id="tavern_sign",
        )
    )
    assert unsupported.success is False
    assert unsupported.code == "UNSUPPORTED_USE"

    with db.connect() as conn:
        state = __import__("json").loads(
            conn.execute(
                "SELECT state_json FROM entities WHERE id = 'bottle_1'"
            ).fetchone()[0]
        )
    assert state["filled_with"] is None


def test_repeated_use_does_not_refill_or_mutate_again(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    buy_bottle(game, player)
    action = CanonicalAction(
        player,
        ActionType.USE,
        item_id="bottle_1",
        target_id="village_well",
    )
    first = game.execute(action, external_id="fill-first")
    second = game.execute(action, external_id="fill-second")

    assert first.success is True
    assert second.success is False
    assert second.code == "ITEM_ALREADY_FILLED"
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE action_type = 'USE'"
        ).fetchone()[0] == 2


def test_buy_and_fill_state_survive_database_restart(tmp_path):
    path = tmp_path / "game.db"
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(path)
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    player = game.register_player("discord-a", "Ren")
    buy_bottle(game, player)
    assert game.execute(
        CanonicalAction(
            player,
            ActionType.USE,
            item_id="bottle_1",
            target_id="village_well",
        ),
        external_id="restart-fill",
    ).success

    reopened = GameDatabase(path)
    reopened.initialize()
    restarted = GameService(reopened, FakeClock(now))
    view = restarted.observe(player)
    bottle = next(entity for entity in view.inventory if entity.id == "bottle_1")
    assert view.coins == 7
    assert bottle.state["filled_with"] == "water"
    with reopened.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 23
