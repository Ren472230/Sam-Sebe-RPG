from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueDecision, DialogueService
from samseberpg.quest import QuestService


class RecordingProvider:
    def __init__(self, decision: DialogueDecision) -> None:
        self.decision = decision
        self.context = None

    def generate(self, context):
        self.context = context
        return self.decision


def make_services(
    tmp_path: Path,
    *,
    player_location: str = "workshop_yard",
    provider=None,
):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc))
    player_id = "player_test"
    now = "2026-09-02T12:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', ?, ?, ?)",
            (player_id, DEFAULT_WORLD_ID, "Ren", player_location, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES (?, ?, ?, 10)",
            (player_id, "local", now),
        )
    quest = QuestService(db, clock)
    return db, DialogueService(db, quest, provider=provider), player_id


def test_mira_context_reads_runtime_profile_and_no_quest(tmp_path: Path) -> None:
    provider = RecordingProvider(DialogueDecision("Работа встала."))
    db, dialogue, player = make_services(tmp_path, provider=provider)
    requested = {"wood_stock": 0, "work_cycles": 1, "requested_wood": True}
    with db.connect() as conn:
        conn.execute(
            "UPDATE npc_runtime_state SET state_json = ? WHERE npc_actor_id = 'npc_mira'",
            (json.dumps(requested),),
        )

    dialogue.talk(player, "Что случилось?", npc_id="npc_mira")

    assert provider.context.npc_id == "npc_mira"
    assert provider.context.display_name == "Мира"
    assert provider.context.runtime_state["requested_wood"] is True
    assert provider.context.quest is None
    assert provider.context.relation == {
        "familiarity": 0,
        "trust": 0,
        "affinity": 0,
        "fear": 0,
        "conflict": 0,
        "romance": 0,
    }


def test_private_dialogue_history_is_pair_scoped(tmp_path: Path) -> None:
    db, dialogue, player = make_services(tmp_path)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO dialogue_turns "
            "(world_id, npc_actor_id, player_actor_id, user_text, npc_text, proposal_json, used_fallback, created_at) "
            "VALUES (?, 'npc_mira', ?, ?, ?, '{}', 0, ?)",
            (
                DEFAULT_WORLD_ID,
                player,
                "Это только между нами",
                "Запомнила.",
                "2026-09-02T12:00:00.000Z",
            ),
        )
        conn.execute(
            "UPDATE actors SET location_id = 'river_edge' WHERE id = ?",
            (player,),
        )

    context = dialogue.build_context(player, "Что знаешь?", npc_id="npc_kaspar")

    joined = " ".join(
        turn.user_text + " " + turn.npc_text for turn in context.recent_dialogue
    )
    assert "только между нами" not in joined


def test_remote_npc_cannot_be_talked_to(tmp_path: Path) -> None:
    _, dialogue, player = make_services(tmp_path)

    with pytest.raises(LookupError, match="not present"):
        dialogue.build_context(player, "Привет", npc_id="npc_oren")


def test_dialogue_turn_persists_across_service_instances(tmp_path: Path) -> None:
    provider = RecordingProvider(DialogueDecision("Я тебя услышала."))
    db, dialogue, player = make_services(tmp_path, provider=provider)

    dialogue.talk(player, "Запомни это", npc_id="npc_mira")

    reloaded = DialogueService(
        db,
        QuestService(
            db,
            FakeClock(datetime(2026, 9, 2, 12, 1, tzinfo=timezone.utc)),
        ),
        provider=RecordingProvider(DialogueDecision("Помню.")),
    )
    context = reloaded.build_context(player, "Помнишь?", npc_id="npc_mira")
    assert [(turn.user_text, turn.npc_text) for turn in context.recent_dialogue] == [
        ("Запомни это", "Я тебя услышала.")
    ]


def test_mira_commitment_is_persisted_without_resolving_wood_request(tmp_path: Path) -> None:
    provider = RecordingProvider(
        DialogueDecision(
            "Договорились.",
            social_action="remember_commitment:bring_useful_wood_to_mira",
        )
    )
    db, dialogue, player = make_services(tmp_path, provider=provider)
    requested = {"wood_stock": 0, "work_cycles": 2, "requested_wood": True}
    with db.connect() as conn:
        conn.execute(
            "UPDATE npc_runtime_state SET state_json = ? WHERE npc_actor_id = 'npc_mira'",
            (json.dumps(requested),),
        )

    decision = dialogue.talk(
        player,
        "Я принесу тебе древесину",
        npc_id="npc_mira",
    )

    assert decision.social_action == "remember_commitment:bring_useful_wood_to_mira"
    with db.connect() as conn:
        fact = conn.execute(
            "SELECT fact FROM npc_memories "
            "WHERE npc_actor_id = 'npc_mira' AND subject_actor_id = ?",
            (player,),
        ).fetchone()
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id = 'npc_mira'"
            ).fetchone()[0]
        )
    assert fact is not None and "promised Mira" in fact[0]
    assert state["requested_wood"] is True
    assert state["wood_stock"] == 0


def test_mira_commitment_is_rejected_when_request_not_active(tmp_path: Path) -> None:
    provider = RecordingProvider(
        DialogueDecision(
            "Ладно.",
            social_action="remember_commitment:bring_useful_wood_to_mira",
        )
    )
    db, dialogue, player = make_services(tmp_path, provider=provider)

    decision = dialogue.talk(
        player,
        "Я принесу древесину",
        npc_id="npc_mira",
    )

    assert decision.used_fallback is True
    assert decision.social_action is None
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_memories "
            "WHERE npc_actor_id = 'npc_mira' AND subject_actor_id = ?",
            (player,),
        ).fetchone()[0] == 0


def test_commitment_for_kaspar_is_rejected(tmp_path: Path) -> None:
    provider = RecordingProvider(
        DialogueDecision(
            "Запомню.",
            social_action="remember_commitment:bring_useful_wood_to_mira",
        )
    )
    _, dialogue, player = make_services(
        tmp_path,
        player_location="river_edge",
        provider=provider,
    )

    decision = dialogue.talk(
        player,
        "Я принесу Мире древесину",
        npc_id="npc_kaspar",
    )

    assert decision.used_fallback is True
    assert decision.social_action is None
