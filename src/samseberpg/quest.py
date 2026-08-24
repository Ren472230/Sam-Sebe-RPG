from __future__ import annotations

import json

from .clock import Clock
from .db import DEFAULT_WORLD_ID, GameDatabase
from .domain import QuestResult, QuestState

QUEST_TYPE = "bring_5_firewood"
GIVER_ID = "npc_oren"
REQUIRED_FIREWOOD = 5
REWARD_COINS = 5
TRUST_REWARD = 10
MEMORY_FACT = "The player brought Oren the requested firewood."


class QuestService:
    def __init__(self, db: GameDatabase, clock: Clock) -> None:
        self.db = db
        self.clock = clock

    def get_state(self, player_id: str) -> QuestState:
        conn = self.db.connect()
        try:
            return self._get_state(conn, player_id)
        finally:
            conn.close()

    def accept(self, player_id: str, external_id: str | None = None) -> QuestResult:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._replay(conn, player_id, external_id)
            if replay is not None:
                conn.execute("COMMIT")
                return replay

            state = self._get_state(conn, player_id)
            if state.status != "available":
                result = self._record_result(
                    conn,
                    player_id,
                    external_id,
                    action_type="QUEST_ACCEPT",
                    success=False,
                    code="ALREADY_ACTIVE" if state.status == "active" else "ALREADY_COMPLETED",
                    summary="Quest is already active." if state.status == "active" else "Quest is already completed.",
                )
                conn.execute("COMMIT")
                return result

            now = _timestamp(self.clock)
            conn.execute(
                "INSERT INTO quests (id, world_id, player_actor_id, quest_type, giver_actor_id, status, accepted_at, completed_at) "
                "VALUES (?, ?, ?, ?, ?, 'active', ?, NULL)",
                (f"{QUEST_TYPE}:{player_id}", DEFAULT_WORLD_ID, player_id, QUEST_TYPE, GIVER_ID, now),
            )
            result = self._record_result(
                conn,
                player_id,
                external_id,
                action_type="QUEST_ACCEPT",
                success=True,
                code="OK",
                summary="Oren asked for five pieces of firewood.",
            )
            conn.execute("COMMIT")
            return result
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def turn_in(self, player_id: str, external_id: str | None = None) -> QuestResult:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            replay = self._replay(conn, player_id, external_id)
            if replay is not None:
                conn.execute("COMMIT")
                return replay

            state = self._get_state(conn, player_id)
            if state.status == "available":
                result = self._record_result(
                    conn,
                    player_id,
                    external_id,
                    action_type="QUEST_TURN_IN",
                    success=False,
                    code="QUEST_NOT_ACTIVE",
                    summary="The firewood quest has not been accepted.",
                )
                conn.execute("COMMIT")
                return result
            if state.status == "completed":
                result = self._record_result(
                    conn,
                    player_id,
                    external_id,
                    action_type="QUEST_TURN_IN",
                    success=False,
                    code="ALREADY_COMPLETED",
                    summary="The firewood quest is already completed.",
                )
                conn.execute("COMMIT")
                return result
            if state.owned_firewood < REQUIRED_FIREWOOD:
                result = self._record_result(
                    conn,
                    player_id,
                    external_id,
                    action_type="QUEST_TURN_IN",
                    success=False,
                    code="INSUFFICIENT_FIREWOOD",
                    summary=f"Oren still needs {REQUIRED_FIREWOOD - state.owned_firewood} more firewood.",
                )
                conn.execute("COMMIT")
                return result

            firewood_ids = [
                str(row[0])
                for row in conn.execute(
                    "SELECT id FROM entities WHERE entity_type = 'firewood' AND owner_actor_id = ? ORDER BY id LIMIT ?",
                    (player_id, REQUIRED_FIREWOOD),
                ).fetchall()
            ]
            conn.executemany(
                "UPDATE entities SET owner_actor_id = ?, location_id = NULL WHERE id = ? AND owner_actor_id = ?",
                [(GIVER_ID, entity_id, player_id) for entity_id in firewood_ids],
            )
            now = _timestamp(self.clock)
            conn.execute(
                "UPDATE quests SET status = 'completed', completed_at = ? "
                "WHERE player_actor_id = ? AND quest_type = ? AND status = 'active'",
                (now, player_id, QUEST_TYPE),
            )
            conn.execute("UPDATE players SET coins = coins + ? WHERE actor_id = ?", (REWARD_COINS, player_id))
            conn.execute(
                "INSERT INTO relations (source_actor_id, target_actor_id, familiarity, trust, affinity, fear, conflict, romance, updated_at) "
                "VALUES (?, ?, 5, ?, 0, 0, 0, 0, ?) "
                "ON CONFLICT(source_actor_id, target_actor_id) DO UPDATE SET "
                "familiarity = familiarity + 5, trust = trust + excluded.trust, updated_at = excluded.updated_at",
                (GIVER_ID, player_id, TRUST_REWARD, now),
            )
            conn.execute(
                "INSERT OR IGNORE INTO npc_memories (npc_actor_id, subject_actor_id, fact, importance, reinforcement_count, created_at) "
                "VALUES (?, ?, ?, 90, 0, ?)",
                (GIVER_ID, player_id, MEMORY_FACT, now),
            )
            result = self._record_result(
                conn,
                player_id,
                external_id,
                action_type="QUEST_TURN_IN",
                success=True,
                code="OK",
                summary="Delivered five firewood to Oren.",
            )
            conn.execute("COMMIT")
            return result
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _get_state(self, conn, player_id: str) -> QuestState:
        if conn.execute("SELECT 1 FROM players WHERE actor_id = ?", (player_id,)).fetchone() is None:
            raise LookupError(f"player not found: {player_id}")
        row = conn.execute(
            "SELECT status FROM quests WHERE player_actor_id = ? AND quest_type = ?",
            (player_id, QUEST_TYPE),
        ).fetchone()
        owned = int(
            conn.execute(
                "SELECT COUNT(*) FROM entities WHERE entity_type = 'firewood' AND owner_actor_id = ?",
                (player_id,),
            ).fetchone()[0]
        )
        return QuestState(
            quest_type=QUEST_TYPE,
            status="available" if row is None else str(row[0]),
            required_firewood=REQUIRED_FIREWOOD,
            owned_firewood=owned,
        )

    def _replay(self, conn, player_id: str, external_id: str | None) -> QuestResult | None:
        if external_id is None:
            return None
        row = conn.execute(
            "SELECT result_json FROM processed_interactions WHERE external_id = ?",
            (external_id,),
        ).fetchone()
        if row is None:
            return None
        stored = json.loads(str(row[0]))
        return QuestResult(
            success=bool(stored["success"]),
            code=str(stored["code"]),
            summary=str(stored["summary"]),
            state=self._get_state(conn, player_id),
            event_id=int(stored["event_id"]),
            replayed=True,
        )

    def _record_result(
        self,
        conn,
        player_id: str,
        external_id: str | None,
        *,
        action_type: str,
        success: bool,
        code: str,
        summary: str,
    ) -> QuestResult:
        location_row = conn.execute("SELECT location_id FROM actors WHERE id = ?", (player_id,)).fetchone()
        location_id = None if location_row is None else str(location_row[0])
        cursor = conn.execute(
            "INSERT INTO action_events (world_id, external_id, occurred_at, actor_id, action_type, target_id, location_id, success, result_code, summary, evidence_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                DEFAULT_WORLD_ID,
                external_id,
                _timestamp(self.clock),
                player_id,
                action_type,
                GIVER_ID,
                location_id,
                int(success),
                code,
                summary,
                json.dumps({"quest_type": QUEST_TYPE}, separators=(",", ":"), sort_keys=True),
            ),
        )
        state = self._get_state(conn, player_id)
        result = QuestResult(
            success=success,
            code=code,
            summary=summary,
            state=state,
            event_id=int(cursor.lastrowid),
        )
        if external_id is not None:
            conn.execute(
                "INSERT INTO processed_interactions (external_id, world_id, actor_id, action_event_id, result_json, processed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    external_id,
                    DEFAULT_WORLD_ID,
                    player_id,
                    result.event_id,
                    json.dumps(
                        {
                            "success": result.success,
                            "code": result.code,
                            "summary": result.summary,
                            "event_id": result.event_id,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    _timestamp(self.clock),
                ),
            )
        return result


def _timestamp(clock: Clock) -> str:
    return clock.now().isoformat(timespec="milliseconds").replace("+00:00", "Z")
