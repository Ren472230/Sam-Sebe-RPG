from __future__ import annotations

import json
from dataclasses import dataclass

from .db import WORLD_ID, to_utc_text
from .game import GameService


NOTABLE_ACTION_TYPES = ("THROW", "GIVE", "BUY")
MAX_DIGEST_EVENTS = 8


@dataclass(frozen=True, slots=True)
class DigestEvent:
    event_id: int
    occurred_at: str
    actor_id: str
    actor_name: str
    action_type: str
    summary: str
    location_id: str | None


@dataclass(frozen=True, slots=True)
class DamagedEntity:
    id: str
    name: str
    location_id: str | None
    condition: int


@dataclass(frozen=True, slots=True)
class DigestNpc:
    id: str
    name: str
    location_id: str
    activity: str


@dataclass(frozen=True, slots=True)
class WorldDigest:
    player_id: str
    generated_at: str
    since_event_id: int
    latest_event_id: int
    events: tuple[DigestEvent, ...]
    omitted_event_count: int
    damaged_entities: tuple[DamagedEntity, ...]
    npcs: tuple[DigestNpc, ...]


class WorldDigestService:
    def __init__(self, game: GameService):
        self.game = game

    def build(self, player_id: str) -> WorldDigest:
        self.game.observe(player_id)
        generated_at = to_utc_text(self.game.clock.now())

        with self.game.db.connect() as conn:
            anchor_row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS id FROM action_events WHERE actor_id = ?",
                (player_id,),
            ).fetchone()
            latest_row = conn.execute(
                "SELECT COALESCE(MAX(id), 0) AS id FROM action_events WHERE world_id = ?",
                (WORLD_ID,),
            ).fetchone()
            since_event_id = int(anchor_row["id"])
            latest_event_id = int(latest_row["id"])

            placeholders = ",".join("?" for _ in NOTABLE_ACTION_TYPES)
            params = (since_event_id, player_id, *NOTABLE_ACTION_TYPES)
            total = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) AS count
                    FROM action_events
                    WHERE id > ?
                      AND actor_id != ?
                      AND success = 1
                      AND action_type IN ({placeholders})
                    """,
                    params,
                ).fetchone()["count"]
            )
            rows = conn.execute(
                f"""
                SELECT
                    e.id,
                    e.occurred_at,
                    e.actor_id,
                    a.name AS actor_name,
                    e.action_type,
                    e.summary,
                    e.location_id
                FROM action_events e
                JOIN actors a ON a.id = e.actor_id
                WHERE e.id > ?
                  AND e.actor_id != ?
                  AND e.success = 1
                  AND e.action_type IN ({placeholders})
                ORDER BY e.id DESC
                LIMIT ?
                """,
                (*params, MAX_DIGEST_EVENTS),
            ).fetchall()
            event_rows = list(reversed(rows))

            damaged: list[DamagedEntity] = []
            for row in conn.execute(
                "SELECT id, name, location_id, state_json FROM entities ORDER BY id"
            ).fetchall():
                try:
                    state = json.loads(row["state_json"])
                except (TypeError, json.JSONDecodeError):
                    continue
                condition = state.get("condition") if isinstance(state, dict) else None
                if (
                    isinstance(condition, int)
                    and not isinstance(condition, bool)
                    and condition < 100
                ):
                    damaged.append(
                        DamagedEntity(
                            id=row["id"],
                            name=row["name"],
                            location_id=row["location_id"],
                            condition=max(0, condition),
                        )
                    )

            npc_rows = conn.execute(
                """
                SELECT a.id, a.name, a.location_id, n.current_activity
                FROM actors a
                JOIN npcs n ON n.actor_id = a.id
                WHERE a.world_id = ?
                ORDER BY a.name, a.id
                """,
                (WORLD_ID,),
            ).fetchall()

        return WorldDigest(
            player_id=player_id,
            generated_at=generated_at,
            since_event_id=since_event_id,
            latest_event_id=latest_event_id,
            events=tuple(
                DigestEvent(
                    event_id=int(row["id"]),
                    occurred_at=row["occurred_at"],
                    actor_id=row["actor_id"],
                    actor_name=row["actor_name"],
                    action_type=row["action_type"],
                    summary=row["summary"],
                    location_id=row["location_id"],
                )
                for row in event_rows
            ),
            omitted_event_count=max(0, total - len(event_rows)),
            damaged_entities=tuple(damaged),
            npcs=tuple(
                DigestNpc(
                    id=row["id"],
                    name=row["name"],
                    location_id=row["location_id"],
                    activity=row["current_activity"],
                )
                for row in npc_rows
            ),
        )
