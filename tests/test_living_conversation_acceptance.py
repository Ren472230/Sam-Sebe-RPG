from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.conversation_state import NpcConversationStateResolver
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueDecision, DialogueService
from samseberpg.game import GameService
from samseberpg.living_conversation import ConversationMemoryCandidate
from samseberpg.npc_profiles import get_npc_profile
from samseberpg.quest import QuestService


ROAD_FACT = (
    "source=npc_wayfarer_1 kind=direct_event: Heavy rain washed out part of "
    "the eastern road, so the next merchant caravan will be delayed. "
    "[confidence=100]"
)


class FixedProvider:
    def __init__(self, decision: DialogueDecision) -> None:
        self.decision = decision

    def generate(self, context):
        return self.decision


def _relation() -> dict[str, int]:
    return {
        "familiarity": 0,
        "trust": 0,
        "affinity": 0,
        "fear": 0,
        "conflict": 0,
        "romance": 0,
    }


def _services(
    tmp_path: Path,
    *,
    provider=None,
    player_id: str = "player_vitality",
) -> tuple[GameDatabase, QuestService, DialogueService, str]:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 7, 17, 0, tzinfo=timezone.utc))
    now = "2026-09-07T17:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ничей', 'workshop_yard', ?)",
            (player_id, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES (?, 'living-conversation-vitality', ?, 10)",
            (player_id, now),
        )
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=provider)
    return db, quest, dialogue, player_id


def test_vitality_profiles_and_same_event_subjective_stances_are_distinct() -> None:
    npc_ids = (
        "npc_oren",
        "npc_mira",
        "npc_kaspar",
        "npc_wayfarer_1",
    )
    profiles = [get_npc_profile(npc_id) for npc_id in npc_ids]
    fingerprints = {
        (
            profile.speech_style,
            profile.temperament,
            profile.humor_style,
            profile.characteristic_phrases,
        )
        for profile in profiles
    }
    assert len(fingerprints) == len(npc_ids)

    resolver = NpcConversationStateResolver()
    states = {
        "npc_oren": resolver.resolve(
            npc_id="npc_oren",
            runtime_state={"bread_requested": True, "bread_received": False},
            activity="running the inn",
            relation=_relation(),
            known_facts=(ROAD_FACT,),
        ),
        "npc_mira": resolver.resolve(
            npc_id="npc_mira",
            runtime_state={"requested_wood": True, "wood_stock": 0},
            activity="working at the bench",
            relation=_relation(),
            known_facts=(ROAD_FACT,),
        ),
        "npc_kaspar": resolver.resolve(
            npc_id="npc_kaspar",
            runtime_state={"goal": "bring_useful_wood_to_mira", "carrying_wood": 0},
            activity="foraging along the river",
            relation=_relation(),
            known_facts=(ROAD_FACT,),
        ),
        "npc_wayfarer_1": resolver.resolve(
            npc_id="npc_wayfarer_1",
            runtime_state={"arrived": True},
            activity="resting after the road",
            relation=_relation(),
            known_facts=(ROAD_FACT,),
        ),
    }

    assert states["npc_oren"].stance == "road_delay_threatens_supplies"
    assert states["npc_mira"].stance == "work_first"
    assert states["npc_kaspar"].stance == "independence_over_promises"
    assert states["npc_wayfarer_1"].stance == "trust_what_i_saw"
    assert len({state.stance for state in states.values()}) == 4


def test_vitality_private_callback_open_thread_survives_restart_and_drives_initiative(
    tmp_path: Path,
) -> None:
    first = DialogueDecision(
        text="И почему ты уехал из столицы?",
        npc_id="npc_mira",
        conversation_act="ask",
        memory_candidates=(
            ConversationMemoryCandidate(
                memory_type="player_claim",
                content="Игрок сказал Мире, что раньше жил в столице.",
            ),
        ),
        open_thread="reason_for_leaving_capital",
    )
    db, quest, dialogue, player = _services(
        tmp_path,
        provider=FixedProvider(first),
    )

    result = dialogue.talk(player, "Я раньше жил в столице.", "npc_mira")
    assert result.used_fallback is False
    assert result.conversation_act == "ask"

    restarted = DialogueService(db, quest, provider=None)
    mira = restarted.build_context(player, "Мы ведь не договорили.", "npc_mira")
    assert [item.content for item in mira.conversation_memories] == [
        "Игрок сказал Мире, что раньше жил в столице."
    ]
    assert mira.thread_state.open_threads == ("reason_for_leaving_capital",)
    assert mira.thread_state.pending_question == "И почему ты уехал из столицы?"
    assert mira.initiative is not None
    assert mira.initiative.kind == "unfinished_thread"
    assert "раньше жил в столице" in mira.to_prompt().lower()

    with db.connect() as conn:
        conn.execute("UPDATE actors SET location_id = 'river_edge' WHERE id = ?", (player,))
    kaspar = restarted.build_context(player, "Что ты обо мне знаешь?", "npc_kaspar")
    assert kaspar.conversation_memories == ()
    assert kaspar.thread_state.open_threads == ()
    assert kaspar.thread_state.pending_question is None
    assert "раньше жил в столице" not in kaspar.to_prompt().lower()


def test_vitality_refusal_act_is_valid_and_preserved(tmp_path: Path) -> None:
    refusal = DialogueDecision(
        text="Нет. В это я вмешиваться не стану.",
        npc_id="npc_mira",
        conversation_act="refuse",
    )
    _, _, dialogue, player = _services(
        tmp_path,
        provider=FixedProvider(refusal),
    )

    result = dialogue.talk(player, "Сделай это за меня.", "npc_mira")

    assert result.used_fallback is False
    assert result.conversation_act == "refuse"
    assert result.text == "Нет. В это я вмешиваться не стану."


def test_vitality_public_dialogue_boundary_hides_internal_relationship_state(
    tmp_path: Path,
) -> None:
    decision = DialogueDecision(
        text="Не сейчас. Я занята работой.",
        npc_id="npc_mira",
        conversation_act="refuse",
        memory_candidates=(
            ConversationMemoryCandidate(
                memory_type="preference",
                content="Игрок предпочитает короткие разговоры.",
            ),
        ),
    )
    db = GameDatabase(tmp_path / "api.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 7, 17, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=FixedProvider(decision))
    client = TestClient(create_app(game, quest, dialogue))
    player = client.post(
        "/api/session",
        json={"external_id": "vitality-public", "name": "Ничей"},
    ).json()["player_id"]

    response = client.post(
        "/api/dialogue",
        json={
            "player_id": player,
            "npc_id": "npc_mira",
            "text": "Поговорим?",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "text",
        "proposal",
        "used_fallback",
        "social_action",
        "npc_id",
    }
    assert payload["text"] == "Не сейчас. Я занята работой."
    assert payload["npc_id"] == "npc_mira"
    serialized = response.text.lower()
    for forbidden in (
        "conversation_act",
        "memory_candidates",
        "relationship_behavior",
        "relation_to_player",
        "familiarity",
        "trust",
        "affinity",
        "fear",
        "conflict",
        "romance",
    ):
        assert forbidden not in serialized
