from __future__ import annotations

import json
import sqlite3

from .db import DEFAULT_WORLD_ID


DELIVERY_FACT_TEXT = (
    "Kaspar personally delivered useful wood to Mira when her workshop was blocked."
)
MIRA_REPORT_FACT_TEXT = (
    "Mira said the player promised to bring useful wood while her workshop was blocked."
)
WAYFARER_NEWS_FACT_KEY = "wayfarer_eastern_road_delay:v1"
WAYFARER_NEWS_FACT_TEXT = (
    "Heavy rain washed out part of the eastern road, so the next merchant "
    "caravan will be delayed."
)
_COMMITMENT_PREFIX = "player_promised_mira_useful_wood:"


class SocialWorldService:
    def process_world_events(
        self,
        conn: sqlite3.Connection,
        events: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        effects: list[dict[str, object]] = []
        for event in events:
            effect = self._process_event(conn, event)
            if effect is not None:
                effects.append(effect)
        return effects

    def _process_event(
        self,
        conn: sqlite3.Connection,
        event: dict[str, object],
    ) -> dict[str, object] | None:
        event_id = event.get("world_event_id")
        tick = event.get("tick")
        data = event.get("data")
        if type(event_id) is not int or type(tick) is not int or not isinstance(data, dict):
            return None

        if (
            event.get("event_type") == "NPC_DELIVERED_RESOURCE"
            and event.get("actor_id") == "npc_kaspar"
            and event.get("target_id") == "npc_mira"
            and data.get("resource_kind") == "useful_wood"
        ):
            return self._process_kaspar_delivery(
                conn,
                event_id=event_id,
                tick=tick,
            )

        if (
            event.get("event_type") == "WAYFARER_ARRIVED"
            and event.get("actor_id") == "npc_wayfarer_1"
            and event.get("target_id") == "npc_oren"
            and event.get("location_id") == "tavern_interior"
            and data.get("route") == "eastern_road"
        ):
            return self._process_wayfarer_arrival(
                conn,
                event_id=event_id,
                tick=tick,
            )

        return None

    def _process_kaspar_delivery(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: int,
        tick: int,
    ) -> dict[str, object] | None:
        canonical = conn.execute(
            "SELECT tick, actor_id, event_type, target_id, location_id, data_json "
            "FROM world_events WHERE id = ? AND world_id = ?",
            (event_id, DEFAULT_WORLD_ID),
        ).fetchone()
        if canonical is None:
            return None
        canonical_data = _decoded_event_data(canonical)
        if canonical_data is None:
            return None
        if not (
            int(canonical["tick"]) == tick
            and str(canonical["actor_id"]) == "npc_kaspar"
            and str(canonical["event_type"]) == "NPC_DELIVERED_RESOURCE"
            and canonical["target_id"] == "npc_mira"
            and canonical_data.get("resource_kind") == "useful_wood"
        ):
            return None
        if self._already_processed(conn, event_id):
            return None

        now = _sqlite_utc_now(conn)
        fact_key = f"kaspar_delivered_useful_wood_to_mira:{event_id}"
        conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
            "source_kind, source_actor_id, source_world_event_id, source_knowledge_id, "
            "confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_mira', 'npc_kaspar', ?, ?, 'direct_event', "
            "'npc_kaspar', ?, NULL, 100, 1, ?, ?) "
            "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
            (
                DEFAULT_WORLD_ID,
                fact_key,
                DELIVERY_FACT_TEXT,
                event_id,
                tick,
                now,
            ),
        )
        conn.execute(
            "INSERT INTO relations "
            "(source_actor_id, target_actor_id, familiarity, trust, affinity, fear, "
            "conflict, romance, updated_at) "
            "VALUES ('npc_mira', 'npc_kaspar', 5, 5, 0, 0, 0, 0, ?) "
            "ON CONFLICT(source_actor_id, target_actor_id) DO UPDATE SET "
            "familiarity = familiarity + 5, trust = trust + 5, updated_at = excluded.updated_at",
            (now,),
        )
        propagated = self._propagate_mira_commitments(conn, tick=tick, now=now)
        self._record_receipt(conn, event_id=event_id, now=now)
        return {
            "world_event_id": event_id,
            "effect_type": "NPC_HELP_RECOGNIZED",
            "knower_actor_id": "npc_mira",
            "subject_actor_id": "npc_kaspar",
            "fact_key": fact_key,
            "propagated_fact_keys": propagated,
        }

    def _process_wayfarer_arrival(
        self,
        conn: sqlite3.Connection,
        *,
        event_id: int,
        tick: int,
    ) -> dict[str, object] | None:
        canonical = conn.execute(
            "SELECT tick, actor_id, event_type, target_id, location_id, data_json "
            "FROM world_events WHERE id = ? AND world_id = ?",
            (event_id, DEFAULT_WORLD_ID),
        ).fetchone()
        if canonical is None:
            return None
        canonical_data = _decoded_event_data(canonical)
        if canonical_data is None:
            return None
        if not (
            int(canonical["tick"]) == tick
            and str(canonical["actor_id"]) == "npc_wayfarer_1"
            and str(canonical["event_type"]) == "WAYFARER_ARRIVED"
            and canonical["target_id"] == "npc_oren"
            and canonical["location_id"] == "tavern_interior"
            and canonical_data.get("route") == "eastern_road"
        ):
            return None
        if self._already_processed(conn, event_id):
            return None

        now = _sqlite_utc_now(conn)
        conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
            "source_kind, source_actor_id, source_world_event_id, source_knowledge_id, "
            "confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_wayfarer_1', NULL, ?, ?, 'direct_event', "
            "'npc_wayfarer_1', ?, NULL, 100, 1, ?, ?) "
            "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
            (
                DEFAULT_WORLD_ID,
                WAYFARER_NEWS_FACT_KEY,
                WAYFARER_NEWS_FACT_TEXT,
                event_id,
                tick,
                now,
            ),
        )
        talen_row = conn.execute(
            "SELECT id FROM npc_knowledge "
            "WHERE knower_actor_id = 'npc_wayfarer_1' AND fact_key = ?",
            (WAYFARER_NEWS_FACT_KEY,),
        ).fetchone()
        if talen_row is None:
            raise RuntimeError("missing canonical Talen road-news knowledge")

        conn.execute(
            "INSERT INTO npc_knowledge "
            "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
            "source_kind, source_actor_id, source_world_event_id, source_knowledge_id, "
            "confidence, shareable, learned_tick, created_at) "
            "VALUES (?, 'npc_oren', NULL, ?, ?, 'npc_report', 'npc_wayfarer_1', ?, ?, "
            "95, 1, ?, ?) "
            "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
            (
                DEFAULT_WORLD_ID,
                WAYFARER_NEWS_FACT_KEY,
                WAYFARER_NEWS_FACT_TEXT,
                event_id,
                int(talen_row["id"]),
                tick,
                now,
            ),
        )
        self._record_receipt(conn, event_id=event_id, now=now)
        return {
            "world_event_id": event_id,
            "effect_type": "WAYFARER_NEWS_SHARED",
            "source_actor_id": "npc_wayfarer_1",
            "recipient_actor_id": "npc_oren",
            "fact_key": WAYFARER_NEWS_FACT_KEY,
        }

    @staticmethod
    def _already_processed(conn: sqlite3.Connection, event_id: int) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM social_processed_events WHERE world_event_id = ?",
                (event_id,),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _record_receipt(
        conn: sqlite3.Connection,
        *,
        event_id: int,
        now: str,
    ) -> None:
        conn.execute(
            "INSERT INTO social_processed_events (world_event_id, processed_at) VALUES (?, ?)",
            (event_id, now),
        )

    @staticmethod
    def _propagate_mira_commitments(
        conn: sqlite3.Connection,
        *,
        tick: int,
        now: str,
    ) -> list[str]:
        rows = conn.execute(
            "SELECT id, subject_actor_id, fact_key FROM npc_knowledge "
            "WHERE knower_actor_id = 'npc_mira' "
            "AND source_kind = 'player_dialogue' "
            "AND shareable = 1 "
            "AND fact_key LIKE ? "
            "ORDER BY id",
            (f"{_COMMITMENT_PREFIX}%",),
        ).fetchall()
        propagated: list[str] = []
        for row in rows:
            subject_actor_id = row["subject_actor_id"]
            fact_key = str(row["fact_key"])
            if subject_actor_id is None or not fact_key.startswith(_COMMITMENT_PREFIX):
                continue
            cursor = conn.execute(
                "INSERT INTO npc_knowledge "
                "(world_id, knower_actor_id, subject_actor_id, fact_key, fact_text, "
                "source_kind, source_actor_id, source_world_event_id, source_knowledge_id, "
                "confidence, shareable, learned_tick, created_at) "
                "VALUES (?, 'npc_kaspar', ?, ?, ?, 'npc_report', 'npc_mira', NULL, ?, "
                "90, 0, ?, ?) "
                "ON CONFLICT(knower_actor_id, fact_key) DO NOTHING",
                (
                    DEFAULT_WORLD_ID,
                    str(subject_actor_id),
                    fact_key,
                    MIRA_REPORT_FACT_TEXT,
                    int(row["id"]),
                    tick,
                    now,
                ),
            )
            if cursor.rowcount == 1:
                propagated.append(fact_key)
        return propagated


def _decoded_event_data(row: sqlite3.Row) -> dict[str, object] | None:
    try:
        data = json.loads(str(row["data_json"]))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _sqlite_utc_now(conn: sqlite3.Connection) -> str:
    return str(
        conn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now')").fetchone()[0]
    )
