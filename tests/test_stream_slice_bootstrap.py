from __future__ import annotations

import json

from samseberpg.db import GameDatabase
from samseberpg.npc_profiles import get_npc_profile


def test_stream_bootstrap_seeds_absent_talen_and_hospitality_state(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    conn = db.connect()
    try:
        talen = conn.execute(
            "SELECT actors.location_id, npcs.role "
            "FROM actors JOIN npcs ON npcs.actor_id = actors.id "
            "WHERE actors.id = 'npc_wayfarer_1'"
        ).fetchone()
        assert talen is not None
        assert talen[0] is None
        assert talen[1] == "wayfarer"

        talen_runtime = conn.execute(
            "SELECT state_json FROM npc_runtime_state "
            "WHERE npc_actor_id = 'npc_wayfarer_1'"
        ).fetchone()
        assert talen_runtime is not None
        assert json.loads(str(talen_runtime[0])) == {"arrived": False}

        oren_runtime = conn.execute(
            "SELECT state_json FROM npc_runtime_state "
            "WHERE npc_actor_id = 'npc_oren'"
        ).fetchone()
        assert oren_runtime is not None
        assert json.loads(str(oren_runtime[0])) == {
            "bread_received": False,
            "bread_requested": False,
        }
    finally:
        conn.close()


def test_talen_profile_is_bounded():
    profile = get_npc_profile("npc_wayfarer_1")

    assert profile.display_name == "Тален"
    assert profile.role == "wayfarer"
    boundaries = " ".join(profile.knowledge_boundaries).lower()
    assert "дорог" in boundaries or "маршрут" in boundaries
