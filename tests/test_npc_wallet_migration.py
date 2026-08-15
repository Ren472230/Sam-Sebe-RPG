from __future__ import annotations

import sqlite3
from pathlib import Path

from samseberpg.db import GameDatabase


def test_fresh_database_gives_seeded_npcs_persistent_wallets(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(npcs)")}
        balances = {
            row["actor_id"]: row["coins"]
            for row in conn.execute("SELECT actor_id, coins FROM npcs ORDER BY actor_id")
        }

    assert "coins" in columns
    assert balances == {"npc_kaspar": 20, "npc_mira": 20, "npc_oren": 20}


def test_reinitialize_never_resets_existing_npc_balance(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    with db.connect() as conn:
        conn.execute("UPDATE npcs SET coins = 37 WHERE actor_id = 'npc_oren'")

    db.initialize()

    with db.connect() as conn:
        coins = conn.execute("SELECT coins FROM npcs WHERE actor_id = 'npc_oren'").fetchone()[0]
    assert coins == 37


def test_initialize_migrates_legacy_npcs_table_without_wallet_column(tmp_path: Path) -> None:
    path = tmp_path / "legacy.sqlite3"
    legacy = sqlite3.connect(path)
    try:
        legacy.execute(
            "CREATE TABLE npcs ("
            "actor_id TEXT PRIMARY KEY, "
            "role TEXT NOT NULL, "
            "current_activity TEXT NOT NULL"
            ")"
        )
        legacy.commit()
    finally:
        legacy.close()

    db = GameDatabase(path)
    db.initialize()

    with db.connect() as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(npcs)")}
        oren = conn.execute(
            "SELECT role, current_activity, coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()
    assert "coins" in columns
    assert tuple(oren) == ("innkeeper", "preparing the inn", 20)
