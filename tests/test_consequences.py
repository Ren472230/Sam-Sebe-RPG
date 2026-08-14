import json
from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path, now=None):
    now = now or datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    return db, game


def test_world_view_exposes_canonical_entity_state(tmp_path):
    _, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")

    workshop = game.observe(player)
    stone = next(entity for entity in workshop.entities if entity.id == "stone_flat_1")
    assert stone.state["throwable"] is True
    assert stone.state["impact_damage"] == 20

    game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square"))
    square = game.observe(player)
    sign = next(entity for entity in square.entities if entity.id == "tavern_sign")
    assert sign.state["condition"] == 100


def take_and_move_to_square(game, player, item_id="stone_flat_1"):
    take = game.execute(CanonicalAction(player, ActionType.TAKE, target_id=item_id))
    assert take.success
    move = game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    )
    assert move.success


def test_throw_requires_owned_throwable_item_and_damageable_present_target(tmp_path):
    _, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")

    not_owned = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="workbench",
        )
    )
    assert not_owned.success is False
    assert not_owned.code == "ITEM_NOT_OWNED"

    assert game.execute(
        CanonicalAction(player, ActionType.TAKE, target_id="bucket_1")
    ).success
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success

    non_throwable = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="bucket_1",
            target_id="tavern_sign",
        )
    )
    assert non_throwable.success is False
    assert non_throwable.code == "ITEM_NOT_THROWABLE"

    absent_target = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="bucket_1",
            target_id="workbench",
        )
    )
    assert absent_target.success is False
    assert absent_target.code in {"ITEM_NOT_THROWABLE", "TARGET_NOT_PRESENT"}


def test_throw_damages_target_drops_projectile_and_records_structured_evidence(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    take_and_move_to_square(game, player)

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="tavern_sign",
        ),
        external_id="throw-sign-1",
    )

    assert result.success is True
    assert result.code == "OK"
    with db.connect() as conn:
        sign_state = json.loads(
            conn.execute(
                "SELECT state_json FROM entities WHERE id = 'tavern_sign'"
            ).fetchone()[0]
        )
        stone = conn.execute(
            "SELECT location_id, owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()
        event = conn.execute(
            "SELECT evidence_json FROM action_events WHERE id = ?", (result.event_id,)
        ).fetchone()

    assert sign_state["condition"] == 80
    assert tuple(stone) == ("village_square", None)
    evidence = json.loads(event["evidence_json"])
    assert evidence["item_id"] == "stone_flat_1"
    assert evidence["target_id"] == "tavern_sign"
    assert evidence["damage"] == 20
    assert evidence["condition_before"] == 100
    assert evidence["condition_after"] == 80


def test_throw_rejects_non_damageable_target_without_moving_projectile(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    take_and_move_to_square(game, player)

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="village_well",
        )
    )

    assert result.success is False
    assert result.code == "TARGET_NOT_DAMAGEABLE"
    with db.connect() as conn:
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()[0]
        sign_state = conn.execute(
            "SELECT state_json FROM entities WHERE id = 'tavern_sign'"
        ).fetchone()[0]
    assert owner == player
    assert '"condition": 100' in sign_state


def test_oren_witnesses_tavern_sign_damage_and_relation_worsens(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    take_and_move_to_square(game, player)

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="tavern_sign",
        )
    )
    assert result.success

    with db.connect() as conn:
        relation = conn.execute(
            """
            SELECT trust, conflict FROM relations
            WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?
            """,
            (player,),
        ).fetchone()
        evidence = json.loads(
            conn.execute(
                "SELECT evidence_json FROM action_events WHERE id = ?",
                (result.event_id,),
            ).fetchone()[0]
        )

    assert tuple(relation) == (-3, 4)
    assert "npc_oren" in evidence["witnesses"]
    assert evidence["relation_deltas"]["npc_oren"] == {
        "trust": -3,
        "conflict": 4,
    }


def test_oren_absent_means_sign_damage_has_no_oren_relation_delta(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    take_and_move_to_square(game, player)

    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE npc_schedule SET location_id = 'river_edge' WHERE npc_actor_id = 'npc_oren'"
        )
        conn.commit()

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="tavern_sign",
        )
    )
    assert result.success

    with db.connect() as conn:
        relation = conn.execute(
            """
            SELECT 1 FROM relations
            WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?
            """,
            (player,),
        ).fetchone()
        evidence = json.loads(
            conn.execute(
                "SELECT evidence_json FROM action_events WHERE id = ?",
                (result.event_id,),
            ).fetchone()[0]
        )

    assert relation is None
    assert "npc_oren" not in evidence["witnesses"]
    assert "npc_oren" not in evidence["relation_deltas"]


def test_throw_damage_and_relation_survive_restart(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    path = tmp_path / "game.db"
    db = GameDatabase(path)
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    player = game.register_player("discord-a", "Ren")
    take_and_move_to_square(game, player)
    assert game.execute(
        CanonicalAction(
            player,
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="tavern_sign",
        )
    ).success

    reopened = GameDatabase(path)
    reopened.initialize()
    restarted = GameService(reopened, FakeClock(now))
    view = restarted.observe(player)
    sign = next(entity for entity in view.entities if entity.id == "tavern_sign")
    assert sign.state["condition"] == 80
    with reopened.connect() as conn:
        relation = conn.execute(
            """
            SELECT trust, conflict FROM relations
            WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?
            """,
            (player,),
        ).fetchone()
    assert tuple(relation) == (-3, 4)


def test_give_food_to_present_npc_transfers_item_and_improves_relation(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success
    assert game.execute(
        CanonicalAction(player, ActionType.TAKE, target_id="bread_1")
    ).success

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.GIVE,
            item_id="bread_1",
            target_id="npc_oren",
        )
    )
    assert result.success is True

    with db.connect() as conn:
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'bread_1'"
        ).fetchone()[0]
        relation = conn.execute(
            """
            SELECT trust, affinity FROM relations
            WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?
            """,
            (player,),
        ).fetchone()
        evidence = json.loads(
            conn.execute(
                "SELECT evidence_json FROM action_events WHERE id = ?",
                (result.event_id,),
            ).fetchone()[0]
        )

    assert owner == "npc_oren"
    assert tuple(relation) == (2, 1)
    assert evidence["item_id"] == "bread_1"
    assert evidence["target_id"] == "npc_oren"
    assert evidence["relation_deltas"]["npc_oren"] == {"trust": 2, "affinity": 1}


def test_give_to_absent_actor_fails_without_transferring_item(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("discord-a", "Ren")
    assert game.execute(
        CanonicalAction(player, ActionType.TAKE, target_id="bucket_1")
    ).success

    result = game.execute(
        CanonicalAction(
            player,
            ActionType.GIVE,
            item_id="bucket_1",
            target_id="npc_kaspar",
        )
    )

    assert result.success is False
    assert result.code == "TARGET_NOT_PRESENT"
    with db.connect() as conn:
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'bucket_1'"
        ).fetchone()[0]
    assert owner == player


def test_give_between_players_transfers_ownership_without_automatic_relation(tmp_path):
    db, game = make_game(tmp_path)
    giver = game.register_player("discord-a", "Ren")
    receiver = game.register_player("discord-b", "Other")
    assert game.execute(
        CanonicalAction(giver, ActionType.TAKE, target_id="rope_1")
    ).success

    result = game.execute(
        CanonicalAction(
            giver,
            ActionType.GIVE,
            item_id="rope_1",
            target_id=receiver,
        )
    )
    assert result.success is True
    assert "rope_1" in {entity.id for entity in game.observe(receiver).inventory}
    with db.connect() as conn:
        relation_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    assert relation_count == 0
