from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from .db import GameDatabase


@dataclass(frozen=True, slots=True)
class ThrowingEvidence:
    attempts: int
    hits: int
    targets: tuple[str, ...]
    projectile_types: tuple[str, ...]
    locations: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "attempts": self.attempts,
            "hits": self.hits,
            "targets": list(self.targets),
            "projectile_types": list(self.projectile_types),
            "locations": list(self.locations),
        }


class BehaviorAnalyzer:
    def __init__(self, db: GameDatabase):
        self.db = db

    def refresh_throwing(
        self, player_id: str, conn: sqlite3.Connection | None = None
    ) -> ThrowingEvidence:
        if conn is None:
            with self.db.connect() as owned_conn:
                return self._refresh_throwing(player_id, owned_conn)
        return self._refresh_throwing(player_id, conn)

    def _refresh_throwing(
        self, player_id: str, conn: sqlite3.Connection
    ) -> ThrowingEvidence:
        rows = conn.execute(
            """
            SELECT evidence_json
            FROM action_events
            WHERE actor_id = ? AND action_type = 'THROW' AND success = 1
            ORDER BY event_id
            """,
            (player_id,),
        ).fetchall()

        hits = 0
        targets: set[str] = set()
        projectile_types: set[str] = set()
        locations: set[str] = set()

        for row in rows:
            evidence = json.loads(row["evidence_json"])
            hits += int(bool(evidence.get("hit", False)))
            if evidence.get("target_id"):
                targets.add(str(evidence["target_id"]))
            if evidence.get("projectile_type"):
                projectile_types.add(str(evidence["projectile_type"]))
            if evidence.get("location_id"):
                locations.add(str(evidence["location_id"]))

        profile = ThrowingEvidence(
            attempts=len(rows),
            hits=hits,
            targets=tuple(sorted(targets)),
            projectile_types=tuple(sorted(projectile_types)),
            locations=tuple(sorted(locations)),
        )
        conn.execute(
            """
            INSERT INTO behavior_profiles(player_id, behavior_key, data_json)
            VALUES (?, 'throwing', ?)
            ON CONFLICT(player_id, behavior_key)
            DO UPDATE SET data_json = excluded.data_json
            """,
            (player_id, json.dumps(profile.as_dict(), ensure_ascii=False)),
        )
        return profile
