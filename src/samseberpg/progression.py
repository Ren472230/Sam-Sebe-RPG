from __future__ import annotations

import json

from .behavior import BehaviorAnalyzer
from .db import GameDatabase
from .domain import MechanicPrimitive, MechanicSpec


class MechanicValidator:
    LIMITS = {
        MechanicPrimitive.MODIFY_ACCURACY: (0.0, 15.0, "ACCURACY_LIMIT_EXCEEDED"),
        MechanicPrimitive.MODIFY_RANGE: (0.0, 10.0, "RANGE_LIMIT_EXCEEDED"),
        MechanicPrimitive.MODIFY_COST: (0.0, 20.0, "COST_LIMIT_EXCEEDED"),
        MechanicPrimitive.MODIFY_QUALITY: (-25.0, 25.0, "QUALITY_LIMIT_EXCEEDED"),
        MechanicPrimitive.MODIFY_RELATION_GAIN: (0.0, 25.0, "RELATION_GAIN_LIMIT_EXCEEDED"),
    }

    def validate(self, spec: MechanicSpec) -> tuple[bool, str]:
        try:
            primitive = (
                spec.primitive
                if isinstance(spec.primitive, MechanicPrimitive)
                else MechanicPrimitive(spec.primitive)
            )
        except (ValueError, TypeError):
            return False, "UNKNOWN_PRIMITIVE"

        if primitive in self.LIMITS:
            low, high, reason = self.LIMITS[primitive]
            if (
                not isinstance(spec.magnitude, (int, float))
                or isinstance(spec.magnitude, bool)
                or not low <= float(spec.magnitude) <= high
            ):
                return False, reason

        if primitive is MechanicPrimitive.UNLOCK_ACTION_VARIANT:
            if not spec.action_family or not spec.variant:
                return False, "INVALID_ACTION_VARIANT"

        if primitive is MechanicPrimitive.CONDITIONAL_MODIFIER and not spec.metadata.get("when"):
            return False, "MISSING_CONDITION"

        if primitive is MechanicPrimitive.REPUTATION_TAG and not spec.metadata.get("tag"):
            return False, "MISSING_REPUTATION_TAG"

        return True, "OK"


class ProgressionService:
    ACHIEVEMENT_ID = "hand_remembers_arc"
    ABILITY_ID = "aimed_throw"

    def __init__(self, db: GameDatabase):
        self.db = db
        self.behavior = BehaviorAnalyzer(db)

    def evaluate(self, player_id: str) -> list[str]:
        evidence = self.behavior.throwing_evidence(player_id)
        qualifies = (
            evidence.attempts >= 12
            and evidence.hits >= 5
            and evidence.distinct_targets >= 3
            and evidence.distinct_projectile_types >= 2
            and evidence.distinct_locations >= 2
        )
        if not qualifies:
            return []

        unlocked: list[str] = []
        world_time = self.db.get_world_time()
        mechanic_specs = [
            MechanicSpec(
                primitive=MechanicPrimitive.UNLOCK_ACTION_VARIANT,
                action_family="THROW",
                variant="aimed",
            ),
            MechanicSpec(
                primitive=MechanicPrimitive.MODIFY_ACCURACY,
                magnitude=10,
                action_family="THROW",
                metadata={"when": {"modifier": "aimed"}},
            ),
        ]
        validator = MechanicValidator()
        for spec in mechanic_specs:
            valid, reason = validator.validate(spec)
            if not valid:
                raise ValueError(f"Built-in mechanic rejected: {reason}")
        mechanic = {
            "specs": [spec.as_dict() for spec in mechanic_specs],
            "allowed_item_tag": "improvised_projectile",
        }
        with self.db.connect() as connection:
            achievement_exists = connection.execute(
                "SELECT 1 FROM achievements WHERE player_id = ? AND achievement_id = ?",
                (player_id, self.ACHIEVEMENT_ID),
            ).fetchone()
            if achievement_exists is None:
                connection.execute(
                    "INSERT INTO achievements(player_id, achievement_id, unlocked_at) VALUES (?, ?, ?)",
                    (player_id, self.ACHIEVEMENT_ID, world_time),
                )
                unlocked.append(self.ACHIEVEMENT_ID)

            ability_exists = connection.execute(
                "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = ?",
                (player_id, self.ABILITY_ID),
            ).fetchone()
            if ability_exists is None:
                connection.execute(
                    """
                    INSERT INTO abilities(player_id, ability_id, unlocked_at, mechanic_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (player_id, self.ABILITY_ID, world_time, json.dumps(mechanic)),
                )
                unlocked.append(self.ABILITY_ID)

        return unlocked
