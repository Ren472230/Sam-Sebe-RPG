from __future__ import annotations

import json
from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import (
    REMEMBER_MIRA_WOOD_COMMITMENT,
    DialogueDecision,
    DialogueService,
)
from samseberpg.quest import QuestService


class CommitmentProvider:
    def generate(self, context):
        return DialogueDecision(
            "Договорились.",
            social_action=REMEMBER_MIRA_WOOD_COMMITMENT,
            npc_id=context.npc_id,
        )


def _setup(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 4, 17, 0, tzinfo=timezone.utc))
    player_id = "player_social_commitment"
    now = "2026-09-04T17:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ren', 'workshop_yard', ?)",
            (player_id, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES (?, 'social-commitment-player', ?, 10)",
            (player_id, now),
        )
        conn.execute(
            "UPDATE npc_runtime_state SET state_json = ? WHERE npc_actor_id = 'npc_mira'",
            (
                json.dumps(
                    {"wood_stock": 0, "work_cycles": 2, "requested_wood": True},
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            ),
        )
    dialogue = DialogueService(db, QuestService(db, clock), provider=CommitmentProvider())
    return db, dialogue, player_id


def test_mira_commitment_creates_one_shareable_knowledge_row(tmp_path):
    db, dialogue, player_id = _setup(tmp_path)
    fact_key = f"player_promised_mira_useful_wood:{player_id}"

    first = dialogue.talk(player_id, "Я принесу тебе древесину", "npc_mira")
    second = dialogue.talk(player_id, "Да, я точно принесу древесину", "npc_mira")

    assert first.social_action == REMEMBER_MIRA_WOOD_COMMITMENT
    assert second.social_action == REMEMBER_MIRA_WOOD_COMMITMENT
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT knower_actor_id, subject_actor_id, fact_key, fact_text, source_kind, "
            "source_actor_id, confidence, shareable, learned_tick "
            "FROM npc_knowledge WHERE fact_key = ? ORDER BY knower_actor_id",
            (fact_key,),
        ).fetchall()
        memory = conn.execute(
            "SELECT reinforcement_count FROM npc_memories "
            "WHERE npc_actor_id = 'npc_mira' AND subject_actor_id = ?",
            (player_id,),
        ).fetchone()

    assert len(rows) == 1
    row = rows[0]
    assert row["knower_actor_id"] == "npc_mira"
    assert row["subject_actor_id"] == player_id
    assert row["fact_key"] == fact_key
    assert "promised Mira" in row["fact_text"]
    assert row["source_kind"] == "player_dialogue"
    assert row["source_actor_id"] == player_id
    assert int(row["confidence"]) == 100
    assert int(row["shareable"]) == 1
    assert int(row["learned_tick"]) >= 0
    assert memory is not None and int(memory["reinforcement_count"]) == 1


def test_commitment_does_not_teach_kaspar_or_oren_immediately(tmp_path):
    db, dialogue, player_id = _setup(tmp_path)
    fact_key = f"player_promised_mira_useful_wood:{player_id}"

    dialogue.talk(player_id, "Я принесу тебе древесину", "npc_mira")

    with db.connect() as conn:
        leaked = int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_knowledge "
                "WHERE knower_actor_id IN ('npc_kaspar', 'npc_oren') AND fact_key = ?",
                (fact_key,),
            ).fetchone()[0]
        )
    assert leaked == 0
