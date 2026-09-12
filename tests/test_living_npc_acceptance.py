from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import (
    DialogueDecision,
    DialogueService,
    REMEMBER_MIRA_WOOD_COMMITMENT,
)
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService

EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


class ScriptedProvider:
    def __init__(self) -> None:
        self.contexts = []

    def generate(self, context):
        self.contexts.append(context)
        if context.npc_id == "npc_mira":
            if "принесу" in context.user_text.lower():
                return DialogueDecision(
                    text="Договорились. Я запомню.",
                    social_action=REMEMBER_MIRA_WOOD_COMMITMENT,
                )
            if bool(context.runtime_state.get("requested_wood")):
                return DialogueDecision(text="Работа встала: мне нужна пригодная древесина.")
            return DialogueDecision(text="Теперь древесина есть, могу снова работать.")
        if context.npc_id == "npc_kaspar":
            return DialogueDecision(text="Я занимаюсь своими делами у реки.")
        return DialogueDecision(text="Слушаю.")


def test_living_npc_primary_route_persists_social_and_world_consequences(
    tmp_path: Path,
) -> None:
    db = GameDatabase(tmp_path / "living-npc.sqlite3")
    db.initialize()
    clock = FakeClock(EVENING)
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    provider = ScriptedProvider()
    dialogue = DialogueService(db, quest, provider=provider)
    player_id = game.register_player("living-npc-player", "Player")

    waited = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 5},
        ),
        external_id="living-npc-wait-request",
    )
    assert waited.success is True

    first = dialogue.talk(player_id, "Что случилось?", npc_id="npc_mira")
    assert "древес" in first.text.lower()
    mira_before = provider.contexts[-1]
    assert mira_before.runtime_state["requested_wood"] is True

    commitment = dialogue.talk(
        player_id,
        "Я принесу тебе древесину",
        npc_id="npc_mira",
    )
    assert commitment.social_action == REMEMBER_MIRA_WOOD_COMMITMENT

    _move(game, player_id, "village_square", "living-npc-to-square")
    _move(game, player_id, "river_edge", "living-npc-to-river")
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="driftwood_1",
        ),
        external_id="living-npc-take-driftwood",
    )
    assert taken.success is True

    _move(game, player_id, "village_square", "living-npc-return-square")
    _move(game, player_id, "workshop_yard", "living-npc-return-workshop")
    given = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="driftwood_1",
            recipient_id="npc_mira",
        ),
        external_id="living-npc-give-driftwood",
    )
    assert given.success is True

    reloaded_provider = ScriptedProvider()
    reloaded_dialogue = DialogueService(
        db,
        QuestService(db, clock),
        provider=reloaded_provider,
    )
    follow_up = reloaded_dialogue.talk(
        player_id,
        "Ну что, теперь всё в порядке?",
        npc_id="npc_mira",
    )
    assert "снова работать" in follow_up.text.lower()
    mira_after = reloaded_provider.contexts[-1]
    assert mira_after.runtime_state["requested_wood"] is False
    assert mira_after.runtime_state["wood_stock"] == 1
    assert any("promised Mira" in memory for memory in mira_after.memories)
    assert any(
        turn.user_text == "Я принесу тебе древесину"
        for turn in mira_after.recent_dialogue
    )

    _move(game, player_id, "village_square", "living-npc-to-kaspar")
    kaspar = reloaded_dialogue.talk(
        player_id,
        "Что здесь происходило?",
        npc_id="npc_kaspar",
    )
    assert kaspar.npc_id == "npc_kaspar"
    kaspar_context = reloaded_provider.contexts[-1]
    private_text = "Я принесу тебе древесину"
    assert all(private_text not in turn.user_text for turn in kaspar_context.recent_dialogue)
    assert all(private_text not in memory for memory in kaspar_context.memories)

    db.initialize()
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM dialogue_turns "
            "WHERE npc_actor_id='npc_mira' AND player_actor_id=?",
            (player_id,),
        ).fetchone()[0] == 3
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_memories "
            "WHERE npc_actor_id='npc_mira' AND subject_actor_id=?",
            (player_id,),
        ).fetchone()[0] == 1
        mira_state = conn.execute(
            "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id='npc_mira'"
        ).fetchone()[0]
        assert '"requested_wood":false' in str(mira_state)


def test_living_npc_alternate_route_kaspar_resolves_problem_without_player(
    tmp_path: Path,
) -> None:
    db = GameDatabase(tmp_path / "living-npc-autonomous.sqlite3")
    db.initialize()
    clock = FakeClock(EVENING)
    game = GameService(db, clock, living_world=LivingWorldService())
    player_id = game.register_player("observer", "Observer")

    waited = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 9},
        ),
        external_id="living-npc-observe-nine",
    )
    assert waited.success is True

    provider = ScriptedProvider()
    dialogue = DialogueService(db, QuestService(db, clock), provider=provider)
    reply = dialogue.talk(
        player_id,
        "Что стало с древесиной?",
        npc_id="npc_mira",
    )
    assert "снова работать" in reply.text.lower()
    context = provider.contexts[-1]
    assert context.runtime_state["requested_wood"] is False
    assert context.runtime_state["wood_stock"] == 1

    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM world_events "
            "WHERE event_type='NPC_DELIVERED_RESOURCE'"
        ).fetchone()[0] == 1


def _move(
    game: GameService,
    player_id: str,
    destination: str,
    external_id: str,
) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.MOVE,
            destination_id=destination,
        ),
        external_id=external_id,
    )
    assert result.success is True
