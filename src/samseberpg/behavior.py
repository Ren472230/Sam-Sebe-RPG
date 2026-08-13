from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .db import GameDatabase


@dataclass(frozen=True, slots=True)
class ThrowingEvidence:
    attempts: int
    hits: int
    distinct_targets: int
    distinct_projectile_types: int
    distinct_locations: int
    aimed_attempts: int
    successful_aimed_attempts: int


class BehaviorAnalyzer:
    PROFILE_KEY = "throwing"

    def __init__(self, db: GameDatabase):
        self.db = db

    def throwing_evidence(self, player_id: str) -> ThrowingEvidence:
        with self.db.connect() as connection:
            rows = connection.execute(
                """
                SELECT target_id, location_id, evidence_json
                FROM action_events
                WHERE actor_id = ? AND action_type = 'THROW' AND success = 1
                ORDER BY event_id
                """,
                (player_id,),
            ).fetchall()

        targets: set[str] = set()
        projectile_types: set[str] = set()
        locations: set[str] = set()
        hits = 0
        aimed_attempts = 0
        successful_aimed_attempts = 0

        for row in rows:
            evidence = json.loads(row["evidence_json"])
            if row["target_id"]:
                targets.add(row["target_id"])
            if row["location_id"]:
                locations.add(row["location_id"])
            if evidence.get("item_kind"):
                projectile_types.add(str(evidence["item_kind"]))
            hit = bool(evidence.get("hit"))
            aimed = bool(evidence.get("aimed"))
            hits += int(hit)
            aimed_attempts += int(aimed)
            successful_aimed_attempts += int(hit and aimed)

        profile = ThrowingEvidence(
            attempts=len(rows),
            hits=hits,
            distinct_targets=len(targets),
            distinct_projectile_types=len(projectile_types),
            distinct_locations=len(locations),
            aimed_attempts=aimed_attempts,
            successful_aimed_attempts=successful_aimed_attempts,
        )
        self._persist(player_id, profile)
        return profile

    def _persist(self, player_id: str, profile: ThrowingEvidence) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO behavior_profiles(player_id, profile_key, profile_json)
                VALUES (?, ?, ?)
                ON CONFLICT(player_id, profile_key)
                DO UPDATE SET profile_json = excluded.profile_json
                """,
                (player_id, self.PROFILE_KEY, json.dumps(asdict(profile))),
            )
