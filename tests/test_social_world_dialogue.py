from __future__ import annotations

from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.quest import QuestService


def _setup_kaspar_dialogue(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 4, 17, 0, tzinfo=timezone.utc))
    player_id = "player_social_dialogue"
    now = "2026-09-04T17:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ren', 'river_edge', ?)",
            (player_id, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES (?, 'social-dialogue-player', ?, 10)",
            (player_id, now),
        )
    return db, DialogueService(db, QuestService(db, clock), provider=None), player_id


def _seed_kaspar_report(db: GameDatabase, player_id: str) -> str:
    fact_key = f"player_promised_mira_useful_wood:{player_id}"
    with db.connect() as conn:
        mira = conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, source_kind, "
            "source_actor_id, confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_mira', ?, ?, ?, 'player_dialogue', ?, 100, 1, 5, ?) ",
            (
                DEFAULT_WORLD_ID,
                player_id,
                fact_key,
                "The player promised Mira to bring useful wood while her workshop was blocked.",
                player_id,
                "2026-09-04T17:00:00.000Z",
            ),
        )
        conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, source_kind, "
            "source_actor_id, source_knowledge_id, confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_kaspar', ?, ?, ?, 'npc_report', 'npc_mira', ?, 90, 0, 9, ?)",
            (
                DEFAULT_WORLD_ID,
                player_id,
                fact_key,
                "Mira said the player promised to bring useful wood while her workshop was blocked.",
                int(mira.lastrowid),
                "2026-09-04T17:01:00.000Z",
            ),
        )
    return fact_key


def test_kaspar_context_contains_only_his_provenance_aware_knowledge(tmp_path):
    db, dialogue, player_id = _setup_kaspar_dialogue(tmp_path)
    _seed_kaspar_report(db, player_id)

    context = dialogue.build_context(player_id, "Что ты обо мне слышал?", "npc_kaspar")

    assert len(context.known_facts) == 1
    assert "Mira said" in context.known_facts[0]
    assert "confidence=90" in context.known_facts[0]
    prompt = context.to_prompt()
    assert "known_facts:" in prompt
    assert "Mira said" in prompt

    with db.connect() as conn:
        conn.execute(
            "UPDATE actors SET location_id = 'tavern_interior' WHERE id = ?",
            (player_id,),
        )
    oren = dialogue.build_context(player_id, "Что ты обо мне слышал?", "npc_oren")
    assert oren.known_facts == ()
    assert "Mira said" not in oren.to_prompt()


def test_kaspar_fallback_mentions_mira_only_after_report_exists(tmp_path):
    db, dialogue, player_id = _setup_kaspar_dialogue(tmp_path)

    before = dialogue.talk(player_id, "Что ты обо мне слышал?", "npc_kaspar")
    assert "Мира говорила" not in before.text

    _seed_kaspar_report(db, player_id)
    after = dialogue.talk(player_id, "Что ты обо мне слышал?", "npc_kaspar")

    assert after.used_fallback is True
    assert "Мира говорила" in after.text
    assert "обещал" in after.text
    assert "древес" in after.text
