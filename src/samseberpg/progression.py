from __future__ import annotations

import json
import sqlite3

from .behavior import BehaviorAnalyzer
from .db import GameDatabase
from .domain import MechanicPrimitive, MechanicSpec


ACHIEVEMENT_ID = "hand_remembers_arc"
ABILITY_ID = "aimed_throw"


class MechanicValidator:
    LIMITS: dict[MechanicPrimitive, float | None] = {
        MechanicPrimitive.MODIFY_ACCURACY: 15.0,
        MechanicPrimitive.MODIFY_RANGE: 10.0,
        MechanicPrimitive.MODIFY_COST: 20.0,
        MechanicPrimitive.MODIFY_QUALITY: None,
        MechanicPrimitive.MODIFY_RELATION_GAIN: 25.0,
        MechanicPrimitive.UNLOCK_ACTION_VARIANT: None,
        MechanicPrimitive.CONDITIONAL_MODIFIER: None,
        MechanicPrimitive.REPUTATION_TAG: None,
    }

    def validate(self, spec: MechanicSpec) -> tuple[bool, str]:
        try:
            primitive = (
                spec.primitive
                if isinstance(spec.primitive, MechanicPrimitive)
                else MechanicPrimitive(spec.primitive)
            )
        except ValueError:
            return False, "UNKNOWN_PRIMITIVE"

        limit = self.LIMITS[primitive]
        if limit is not None:
            if not isinstance(spec.value, (int, float)) or isinstance(spec.value, bool):
                return False, "INVALID_VALUE"
            if abs(float(spec.value)) > limit:
                return False, "LIMIT_EXCEEDED"
        return True, "OK"


class ProgressionService:
    def __init__(self, db: GameDatabase):
        self.db = db
        self.behavior = BehaviorAnalyzer(db)

    def evaluate(
        self, player_id: str, conn: sqlite3.Connection | None = None
    ) -> list[str]:
        if conn is None:
            with self.db.connect() as owned_conn:
                return self._evaluate(player_id, owned_conn)
        return self._evaluate(player_id, conn)

    def _evaluate(self, player_id: str, conn: sqlite3.Connection) -> list[str]:
        evidence = self.behavior.refresh_throwing(player_id, conn)
        qualifies = (
            evidence.attempts >= 12
            and evidence.hits >= 5
            and len(evidence.targets) >= 3
            and len(evidence.projectile_types) >= 2
            and len(evidence.locations) >= 2
        )
        if not qualifies:
            return []

        world_time_row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        world_time = int(world_time_row["value"]) if world_time_row else 0
        unlocked: list[str] = []

        achievement_exists = conn.execute(
            "SELECT 1 FROM achievements WHERE player_id = ? AND achievement_id = ?",
            (player_id, ACHIEVEMENT_ID),
        ).fetchone()
        if achievement_exists is None:
            conn.execute(
                "INSERT INTO achievements(player_id, achievement_id, unlocked_at) VALUES (?, ?, ?)",
                (player_id, ACHIEVEMENT_ID, world_time),
            )
            unlocked.append(ACHIEVEMENT_ID)

        ability_exists = conn.execute(
            "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = ?",
            (player_id, ABILITY_ID),
        ).fetchone()
        if ability_exists is None:
            mechanic_spec = MechanicSpec(
                primitive=MechanicPrimitive.MODIFY_ACCURACY,
                value=10,
                action="THROW",
                variant="aimed",
            )
            valid, reason = MechanicValidator().validate(mechanic_spec)
            if not valid:
                raise ValueError(f"Built-in mechanic rejected: {reason}")
            mechanic = mechanic_spec.to_dict()
            conn.execute(
                """
                INSERT INTO abilities(player_id, ability_id, mechanic_json, unlocked_at)
                VALUES (?, ?, ?, ?)
                """,
                (player_id, ABILITY_ID, json.dumps(mechanic), world_time),
            )
            unlocked.append(ABILITY_ID)

        return unlocked
