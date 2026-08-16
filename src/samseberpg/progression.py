from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

from .domain import MechanicPrimitive, MechanicSpec


ACHIEVEMENT_ID = "hand_remembers_arc"
ABILITY_ID = "aimed_throw"
AIMED_THROW_SPEC = MechanicSpec(
    mechanic_id=ABILITY_ID,
    primitive=MechanicPrimitive.MODIFY_ACCURACY,
    magnitude=0.10,
)


@dataclass(frozen=True, slots=True)
class ThrowingEvidence:
    attempts: int
    hits: int
    distinct_targets: int
    distinct_projectile_types: int
    distinct_locations: int

    def qualifies(self) -> bool:
        return (
            self.attempts >= 12
            and self.hits >= 5
            and self.distinct_targets >= 3
            and self.distinct_projectile_types >= 2
            and self.distinct_locations >= 2
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


class MechanicValidator:
    _NUMERIC_LIMITS = {
        MechanicPrimitive.MODIFY_ACCURACY: 0.15,
        MechanicPrimitive.MODIFY_RANGE: 0.10,
        MechanicPrimitive.MODIFY_COST: 0.20,
        MechanicPrimitive.MODIFY_RELATION_GAIN: 0.25,
    }

    def validate(self, spec: MechanicSpec) -> tuple[bool, str]:
        if not isinstance(spec.primitive, MechanicPrimitive):
            return False, "UNKNOWN_PRIMITIVE"

        limit = self._NUMERIC_LIMITS.get(spec.primitive)
        if limit is None:
            if spec.magnitude is not None:
                return False, "INVALID_MAGNITUDE"
            return True, "OK"

        magnitude = spec.magnitude
        if (
            isinstance(magnitude, bool)
            or not isinstance(magnitude, (int, float))
            or not math.isfinite(float(magnitude))
            or float(magnitude) < 0.0
        ):
            return False, "INVALID_MAGNITUDE"
        if float(magnitude) > limit:
            return False, "LIMIT_EXCEEDED"
        return True, "OK"


class ProgressionService:
    def __init__(self, validator: MechanicValidator | None = None) -> None:
        self.validator = validator or MechanicValidator()

    def evaluate_throwing(
        self, conn, actor_id: str, unlocked_at: str
    ) -> tuple[str, ...]:
        evidence = self._throwing_evidence(conn, actor_id)
        if not evidence.qualifies():
            return ()

        payload = json.dumps(
            evidence.to_dict(), separators=(",", ":"), sort_keys=True
        )
        achievement_insert = conn.execute(
            "INSERT OR IGNORE INTO achievements "
            "(actor_id, achievement_id, unlocked_at, evidence_json) "
            "VALUES (?, ?, ?, ?)",
            (actor_id, ACHIEVEMENT_ID, unlocked_at, payload),
        )

        ability_insert = None
        mechanic_valid, _ = self.validator.validate(AIMED_THROW_SPEC)
        if mechanic_valid:
            ability_insert = conn.execute(
                "INSERT OR IGNORE INTO abilities "
                "(actor_id, ability_id, source_achievement_id, unlocked_at) "
                "VALUES (?, ?, ?, ?)",
                (actor_id, ABILITY_ID, ACHIEVEMENT_ID, unlocked_at),
            )

        unlocked: list[str] = []
        if achievement_insert.rowcount:
            unlocked.append(ACHIEVEMENT_ID)
        if ability_insert is not None and ability_insert.rowcount:
            unlocked.append(ABILITY_ID)
        return tuple(unlocked)

    def _throwing_evidence(self, conn, actor_id: str) -> ThrowingEvidence:
        rows = conn.execute(
            "SELECT target_id, location_id, evidence_json FROM action_events "
            "WHERE actor_id = ? AND action_type = 'THROW' AND success = 1 ORDER BY id",
            (actor_id,),
        ).fetchall()

        hits = 0
        targets: set[str] = set()
        projectile_types: set[str] = set()
        locations: set[str] = set()
        for row in rows:
            event_evidence = json.loads(str(row[2]))
            if bool(event_evidence.get("hit")):
                hits += 1
            if row[0] is not None:
                targets.add(str(row[0]))
            projectile_type = event_evidence.get("projectile_type")
            if projectile_type is not None:
                projectile_types.add(str(projectile_type))
            if row[1] is not None:
                locations.add(str(row[1]))

        return ThrowingEvidence(
            attempts=len(rows),
            hits=hits,
            distinct_targets=len(targets),
            distinct_projectile_types=len(projectile_types),
            distinct_locations=len(locations),
        )
