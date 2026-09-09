from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.dialogue import DialogueService, REMEMBER_MIRA_WOOD_COMMITMENT
from samseberpg.quest import QuestService


def test_offline_mira_fallback_can_recognize_explicit_wood_commitment(
    tmp_path: Path,
) -> None:
    db = GameDatabase(tmp_path / "fallback-commitment.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc))
    player = "player_fallback"
    now = "2026-09-02T12:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES (?, ?, 'player', 'Ren', 'workshop_yard', ?)",
            (player, DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES (?, 'fallback', ?, 10)",
            (player, now),
        )
        conn.execute(
            "UPDATE npc_runtime_state SET state_json = ? WHERE npc_actor_id = 'npc_mira'",
            (
                json.dumps(
                    {"wood_stock": 0, "work_cycles": 2, "requested_wood": True}
                ),
            ),
        )
    dialogue = DialogueService(db, QuestService(db, clock), provider=None)

    decision = dialogue.talk(
        player,
        "Я принесу тебе древесину",
        npc_id="npc_mira",
    )

    assert decision.used_fallback is True
    assert decision.social_action == REMEMBER_MIRA_WOOD_COMMITMENT
    with db.connect() as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM npc_memories "
            "WHERE npc_actor_id='npc_mira' AND subject_actor_id=?",
            (player,),
        ).fetchone()[0] == 1
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM npc_runtime_state "
                "WHERE npc_actor_id='npc_mira'"
            ).fetchone()[0]
        )
    assert state == {"wood_stock": 0, "work_cycles": 2, "requested_wood": True}
