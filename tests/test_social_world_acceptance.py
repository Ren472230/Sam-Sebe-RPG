from __future__ import annotations

from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService, player_mira_commitment_fact_key
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService
from samseberpg.social_world import SocialWorldService


EVENING = datetime(2026, 9, 4, 17, 0, tzinfo=timezone.utc)


def _services(tmp_path, name: str):
    db = GameDatabase(tmp_path / name)
    db.initialize()
    clock = FakeClock(EVENING)
    game = GameService(
        db,
        clock,
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    dialogue = DialogueService(db, QuestService(db, clock), provider=None)
    return db, clock, game, dialogue


def _move(game: GameService, player_id: str, destination: str, external_id: str):
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.MOVE,
            destination_id=destination,
        ),
        external_id=external_id,
    )
    assert result.success is True


def test_social_world_primary_route_spreads_fact_only_after_real_delivery_contact_and_persists(tmp_path):
    db, clock, game, dialogue = _services(tmp_path, "social-primary.sqlite3")
    player_id = game.register_player("social-primary-player", "Ren")
    fact_key = player_mira_commitment_fact_key(player_id)

    request = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 5},
        ),
        external_id="social-request-five",
    )
    assert request.success is True

    commitment = dialogue.talk(
        player_id,
        "Я принесу тебе древесину",
        npc_id="npc_mira",
    )
    assert commitment.social_action is not None

    with db.connect() as conn:
        mira = conn.execute(
            "SELECT source_kind, source_actor_id, confidence, shareable "
            "FROM npc_knowledge WHERE knower_actor_id='npc_mira' AND fact_key=?",
            (fact_key,),
        ).fetchone()
        leaked = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge "
                "WHERE knower_actor_id IN ('npc_kaspar','npc_oren') AND fact_key=?",
                (fact_key,),
            ).fetchone()[0]
        )
    assert mira is not None
    assert mira["source_kind"] == "player_dialogue"
    assert mira["source_actor_id"] == player_id
    assert int(mira["confidence"]) == 100
    assert int(mira["shareable"]) == 1
    assert leaked == 0

    _move(game, player_id, "village_square", "social-pre-square")
    _move(game, player_id, "river_edge", "social-pre-river")
    before = dialogue.talk(
        player_id,
        "Что ты обо мне слышал?",
        npc_id="npc_kaspar",
    )
    assert "Мира говорила" not in before.text

    delivery = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 4},
        ),
        external_id="social-delivery-four",
    )
    assert delivery.success is True

    with db.connect() as conn:
        delivery_events = int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events WHERE event_type='NPC_DELIVERED_RESOURCE' "
                "AND actor_id='npc_kaspar' AND target_id='npc_mira'"
            ).fetchone()[0]
        )
        direct = conn.execute(
            "SELECT source_kind, source_actor_id, confidence FROM npc_knowledge "
            "WHERE knower_actor_id='npc_mira' "
            "AND fact_key LIKE 'kaspar_delivered_useful_wood_to_mira:%'"
        ).fetchone()
        relation = conn.execute(
            "SELECT familiarity, trust FROM relations "
            "WHERE source_actor_id='npc_mira' AND target_actor_id='npc_kaspar'"
        ).fetchone()
        kaspar = conn.execute(
            "SELECT source_kind, source_actor_id, source_knowledge_id, confidence, shareable "
            "FROM npc_knowledge WHERE knower_actor_id='npc_kaspar' AND fact_key=?",
            (fact_key,),
        ).fetchone()
        oren = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge WHERE knower_actor_id='npc_oren' AND fact_key=?",
                (fact_key,),
            ).fetchone()[0]
        )
        receipt_count = int(
            conn.execute("SELECT COUNT(*) FROM social_processed_events").fetchone()[0]
        )

    assert delivery_events == 1
    assert direct is not None
    assert direct["source_kind"] == "direct_event"
    assert direct["source_actor_id"] == "npc_kaspar"
    assert int(direct["confidence"]) == 100
    assert relation is not None and tuple(int(value) for value in relation) == (5, 5)
    assert kaspar is not None
    assert kaspar["source_kind"] == "npc_report"
    assert kaspar["source_actor_id"] == "npc_mira"
    assert kaspar["source_knowledge_id"] is not None
    assert int(kaspar["confidence"]) == 90
    assert int(kaspar["shareable"]) == 0
    assert oren == 0
    assert receipt_count == 1

    _move(game, player_id, "village_square", "social-post-square")
    after = dialogue.talk(
        player_id,
        "Что ты обо мне слышал?",
        npc_id="npc_kaspar",
    )
    assert "Мира говорила" in after.text
    assert "обещал" in after.text

    db.initialize()
    reloaded_dialogue = DialogueService(db, QuestService(db, clock), provider=None)
    persisted = reloaded_dialogue.talk(
        player_id,
        "Что ты обо мне слышал?",
        npc_id="npc_kaspar",
    )
    assert "Мира говорила" in persisted.text
    assert "обещал" in persisted.text
    with db.connect() as conn:
        relation_after_reload = conn.execute(
            "SELECT familiarity, trust FROM relations "
            "WHERE source_actor_id='npc_mira' AND target_actor_id='npc_kaspar'"
        ).fetchone()
        kaspar_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge "
                "WHERE knower_actor_id='npc_kaspar' AND fact_key=?",
                (fact_key,),
            ).fetchone()[0]
        )
    assert relation_after_reload is not None
    assert tuple(int(value) for value in relation_after_reload) == (5, 5)
    assert kaspar_count == 1


def test_player_give_without_kaspar_delivery_does_not_spread_mira_commitment(tmp_path):
    db, _, game, dialogue = _services(tmp_path, "social-no-contact.sqlite3")
    player_id = game.register_player("social-no-contact-player", "Ren")
    fact_key = player_mira_commitment_fact_key(player_id)

    waited = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 5},
        ),
        external_id="social-no-contact-five",
    )
    assert waited.success is True
    dialogue.talk(player_id, "Я принесу тебе древесину", npc_id="npc_mira")

    _move(game, player_id, "village_square", "social-no-contact-square")
    _move(game, player_id, "river_edge", "social-no-contact-river")
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="driftwood_1",
        ),
        external_id="social-no-contact-take",
    )
    assert taken.success is True
    _move(game, player_id, "village_square", "social-no-contact-return-square")
    _move(game, player_id, "workshop_yard", "social-no-contact-workshop")
    given = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="driftwood_1",
            recipient_id="npc_mira",
        ),
        external_id="social-no-contact-give",
    )
    assert given.success is True

    with db.connect() as conn:
        delivery_events = int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events WHERE event_type='NPC_DELIVERED_RESOURCE'"
            ).fetchone()[0]
        )
        kaspar = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge WHERE knower_actor_id='npc_kaspar' AND fact_key=?",
                (fact_key,),
            ).fetchone()[0]
        )
        oren = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge WHERE knower_actor_id='npc_oren' AND fact_key=?",
                (fact_key,),
            ).fetchone()[0]
        )
        social_receipts = int(
            conn.execute("SELECT COUNT(*) FROM social_processed_events").fetchone()[0]
        )
    assert delivery_events == 0
    assert kaspar == 0
    assert oren == 0
    assert social_receipts == 0
