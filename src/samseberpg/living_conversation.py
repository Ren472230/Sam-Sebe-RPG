from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3


_ALLOWED_MEMORY_TYPES = {
    "player_claim",
    "preference",
    "commitment",
    "significant_interaction",
}
_ALLOWED_SOURCE_KINDS = {"player_said", "validated_event"}


@dataclass(frozen=True, slots=True)
class ConversationMemoryCandidate:
    memory_type: str
    content: str


@dataclass(frozen=True, slots=True)
class ConversationMemory:
    id: int
    memory_type: str
    content: str
    source_kind: str
    importance: int
    created_tick: int
    reinforcement_count: int


@dataclass(frozen=True, slots=True)
class ConversationThreadState:
    last_topic: str | None
    open_threads: tuple[str, ...]
    pending_question: str | None
    last_seen_tick: int
    turn_count: int


class LivingConversationStore:
    def ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                world_id TEXT NOT NULL,
                npc_actor_id TEXT NOT NULL,
                player_actor_id TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                importance INTEGER NOT NULL DEFAULT 50,
                created_tick INTEGER NOT NULL DEFAULT 0,
                reinforcement_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE(npc_actor_id, player_actor_id, memory_type, content),
                FOREIGN KEY (world_id) REFERENCES worlds(id),
                FOREIGN KEY (npc_actor_id) REFERENCES actors(id),
                FOREIGN KEY (player_actor_id) REFERENCES actors(id)
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_memories_pair
                ON conversation_memories(npc_actor_id, player_actor_id, importance DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS npc_player_conversation_state (
                npc_actor_id TEXT NOT NULL,
                player_actor_id TEXT NOT NULL,
                last_topic TEXT,
                open_threads_json TEXT NOT NULL DEFAULT '[]',
                pending_question TEXT,
                last_seen_tick INTEGER NOT NULL DEFAULT 0,
                turn_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (npc_actor_id, player_actor_id),
                FOREIGN KEY (npc_actor_id) REFERENCES actors(id),
                FOREIGN KEY (player_actor_id) REFERENCES actors(id)
            )
            """
        )

    def add_memory(
        self,
        conn: sqlite3.Connection,
        *,
        world_id: str,
        npc_actor_id: str,
        player_actor_id: str,
        memory_type: str,
        content: str,
        source_kind: str,
        importance: int,
        created_tick: int,
    ) -> None:
        memory_type = memory_type.strip()
        content = content.strip()
        source_kind = source_kind.strip()
        if memory_type not in _ALLOWED_MEMORY_TYPES:
            raise ValueError(f"unsupported conversation memory type: {memory_type}")
        if source_kind not in _ALLOWED_SOURCE_KINDS:
            raise ValueError(f"unsupported conversation memory source: {source_kind}")
        if not content or len(content) > 240:
            raise ValueError("conversation memory content must be 1..240 characters")
        if isinstance(importance, bool) or not isinstance(importance, int) or not 0 <= importance <= 100:
            raise ValueError("conversation memory importance must be an integer from 0 to 100")
        if isinstance(created_tick, bool) or not isinstance(created_tick, int) or created_tick < 0:
            raise ValueError("conversation memory tick must be a non-negative integer")

        self.ensure_schema(conn)
        now = _sqlite_now(conn)
        conn.execute(
            "INSERT INTO conversation_memories "
            "(world_id, npc_actor_id, player_actor_id, memory_type, content, source_kind, "
            "importance, created_tick, reinforcement_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?) "
            "ON CONFLICT(npc_actor_id, player_actor_id, memory_type, content) DO UPDATE SET "
            "reinforcement_count = reinforcement_count + 1, "
            "importance = MAX(importance, excluded.importance), "
            "created_tick = MAX(created_tick, excluded.created_tick)",
            (
                world_id,
                npc_actor_id,
                player_actor_id,
                memory_type,
                content,
                source_kind,
                importance,
                created_tick,
                now,
            ),
        )

    def list_memories(
        self,
        conn: sqlite3.Connection,
        npc_actor_id: str,
        player_actor_id: str,
        *,
        limit: int = 6,
    ) -> tuple[ConversationMemory, ...]:
        self.ensure_schema(conn)
        bounded_limit = max(1, min(int(limit), 12))
        rows = conn.execute(
            "SELECT id, memory_type, content, source_kind, importance, created_tick, reinforcement_count "
            "FROM conversation_memories WHERE npc_actor_id = ? AND player_actor_id = ? "
            "ORDER BY importance DESC, reinforcement_count DESC, id DESC LIMIT ?",
            (npc_actor_id, player_actor_id, bounded_limit),
        ).fetchall()
        return tuple(
            ConversationMemory(
                id=int(row[0]),
                memory_type=str(row[1]),
                content=str(row[2]),
                source_kind=str(row[3]),
                importance=int(row[4]),
                created_tick=int(row[5]),
                reinforcement_count=int(row[6]),
            )
            for row in rows
        )

    def get_thread_state(
        self,
        conn: sqlite3.Connection,
        npc_actor_id: str,
        player_actor_id: str,
    ) -> ConversationThreadState:
        self.ensure_schema(conn)
        row = conn.execute(
            "SELECT last_topic, open_threads_json, pending_question, last_seen_tick, turn_count "
            "FROM npc_player_conversation_state WHERE npc_actor_id = ? AND player_actor_id = ?",
            (npc_actor_id, player_actor_id),
        ).fetchone()
        if row is None:
            return ConversationThreadState(None, (), None, 0, 0)
        raw_threads = json.loads(str(row[1]))
        if not isinstance(raw_threads, list):
            raw_threads = []
        threads = tuple(str(item) for item in raw_threads if isinstance(item, str) and item.strip())[:3]
        return ConversationThreadState(
            last_topic=None if row[0] is None else str(row[0]),
            open_threads=threads,
            pending_question=None if row[2] is None else str(row[2]),
            last_seen_tick=int(row[3]),
            turn_count=int(row[4]),
        )

    def note_turn(
        self,
        conn: sqlite3.Connection,
        *,
        npc_actor_id: str,
        player_actor_id: str,
        last_topic: str | None,
        tick: int,
        pending_question: str | None = None,
    ) -> None:
        self.ensure_schema(conn)
        current = self.get_thread_state(conn, npc_actor_id, player_actor_id)
        topic = _bounded_optional(last_topic, 120, "last_topic")
        question = _bounded_optional(pending_question, 240, "pending_question")
        conn.execute(
            "INSERT INTO npc_player_conversation_state "
            "(npc_actor_id, player_actor_id, last_topic, open_threads_json, pending_question, "
            "last_seen_tick, turn_count, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(npc_actor_id, player_actor_id) DO UPDATE SET "
            "last_topic = excluded.last_topic, pending_question = excluded.pending_question, "
            "last_seen_tick = excluded.last_seen_tick, turn_count = excluded.turn_count, "
            "updated_at = excluded.updated_at",
            (
                npc_actor_id,
                player_actor_id,
                topic,
                json.dumps(current.open_threads, ensure_ascii=False),
                question,
                int(tick),
                current.turn_count + 1,
                _sqlite_now(conn),
            ),
        )

    def open_thread(
        self,
        conn: sqlite3.Connection,
        *,
        npc_actor_id: str,
        player_actor_id: str,
        thread: str,
        tick: int,
    ) -> None:
        self.ensure_schema(conn)
        normalized = _bounded_required(thread, 180, "thread")
        current = self.get_thread_state(conn, npc_actor_id, player_actor_id)
        threads = list(current.open_threads)
        if normalized not in threads:
            threads.append(normalized)
        threads = threads[-3:]
        self._write_thread_state(
            conn,
            npc_actor_id=npc_actor_id,
            player_actor_id=player_actor_id,
            last_topic=current.last_topic,
            open_threads=tuple(threads),
            pending_question=current.pending_question,
            last_seen_tick=int(tick),
            turn_count=current.turn_count,
        )

    def resolve_thread(
        self,
        conn: sqlite3.Connection,
        *,
        npc_actor_id: str,
        player_actor_id: str,
        thread: str,
        tick: int,
    ) -> None:
        self.ensure_schema(conn)
        normalized = _bounded_required(thread, 180, "thread")
        current = self.get_thread_state(conn, npc_actor_id, player_actor_id)
        remaining = tuple(item for item in current.open_threads if item != normalized)
        self._write_thread_state(
            conn,
            npc_actor_id=npc_actor_id,
            player_actor_id=player_actor_id,
            last_topic=current.last_topic,
            open_threads=remaining,
            pending_question=current.pending_question if remaining else None,
            last_seen_tick=int(tick),
            turn_count=current.turn_count,
        )

    def _write_thread_state(
        self,
        conn: sqlite3.Connection,
        *,
        npc_actor_id: str,
        player_actor_id: str,
        last_topic: str | None,
        open_threads: tuple[str, ...],
        pending_question: str | None,
        last_seen_tick: int,
        turn_count: int,
    ) -> None:
        conn.execute(
            "INSERT INTO npc_player_conversation_state "
            "(npc_actor_id, player_actor_id, last_topic, open_threads_json, pending_question, "
            "last_seen_tick, turn_count, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(npc_actor_id, player_actor_id) DO UPDATE SET "
            "last_topic = excluded.last_topic, open_threads_json = excluded.open_threads_json, "
            "pending_question = excluded.pending_question, last_seen_tick = excluded.last_seen_tick, "
            "turn_count = excluded.turn_count, updated_at = excluded.updated_at",
            (
                npc_actor_id,
                player_actor_id,
                last_topic,
                json.dumps(open_threads, ensure_ascii=False),
                pending_question,
                int(last_seen_tick),
                int(turn_count),
                _sqlite_now(conn),
            ),
        )


def _bounded_required(value: str, max_length: int, label: str) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > max_length:
        raise ValueError(f"{label} must be 1..{max_length} characters")
    return normalized


def _bounded_optional(value: str | None, max_length: int, label: str) -> str | None:
    if value is None:
        return None
    return _bounded_required(value, max_length, label)


def _sqlite_now(conn: sqlite3.Connection) -> str:
    return str(conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0])
