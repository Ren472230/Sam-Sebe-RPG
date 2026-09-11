from __future__ import annotations

from samseberpg.db import GameDatabase
from samseberpg.living_conversation import LivingConversationStore


def test_ensure_schema_preserves_active_transaction(tmp_path) -> None:
    db = GameDatabase(tmp_path / "conversation-transaction.sqlite3")
    db.initialize()
    store = LivingConversationStore()
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        assert conn.in_transaction

        store.ensure_schema(conn)

        assert conn.in_transaction, "schema setup must not commit the caller-owned transaction"
    finally:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        conn.close()
