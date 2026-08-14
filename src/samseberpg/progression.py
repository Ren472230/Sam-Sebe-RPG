from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    code: str
    name: str
    description: str


@dataclass(frozen=True, slots=True)
class AbilityDefinition:
    code: str
    name: str
    description: str
    source_achievement_code: str


@dataclass(frozen=True, slots=True)
class ProgressionUnlock:
    kind: str
    code: str
    name: str


ACHIEVEMENTS = {
    "THROWING_HABIT_1": AchievementDefinition(
        code="THROWING_HABIT_1",
        name="Рука помнит дугу",
        description="Повторяющееся метание разных предметов стало узнаваемой привычкой.",
    )
}

ABILITIES = {
    "STEADY_HAND": AbilityDefinition(
        code="STEADY_HAND",
        name="Твёрдая рука",
        description="Освоенная техника добавляет 5 единиц импульса будущим броскам.",
        source_achievement_code="THROWING_HABIT_1",
    )
}


class ProgressionEngine:
    """Deterministic progression derived from canonical action evidence."""

    def evaluate_after_event(
        self,
        conn,
        player_id: str,
        event_id: int,
        now_text: str,
    ) -> tuple[ProgressionUnlock, ...]:
        trigger = conn.execute(
            """
            SELECT id, action_type, success
            FROM action_events
            WHERE id = ? AND actor_id = ?
            """,
            (event_id, player_id),
        ).fetchone()
        if trigger is None or trigger["action_type"] != "THROW" or not trigger["success"]:
            return ()

        existing = conn.execute(
            """
            SELECT 1
            FROM player_achievements
            WHERE player_actor_id = ? AND achievement_code = 'THROWING_HABIT_1'
            """,
            (player_id,),
        ).fetchone()
        if existing is not None:
            return ()

        rows = conn.execute(
            """
            SELECT evidence_json
            FROM action_events
            WHERE actor_id = ? AND action_type = 'THROW' AND success = 1
            ORDER BY id
            """,
            (player_id,),
        ).fetchall()
        projectile_ids: list[str] = []
        for row in rows:
            try:
                evidence = json.loads(row["evidence_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            item_id = evidence.get("item_id") if isinstance(evidence, dict) else None
            if isinstance(item_id, str) and item_id:
                projectile_ids.append(item_id)

        distinct_projectiles = sorted(set(projectile_ids))
        if len(projectile_ids) < 3 or len(distinct_projectiles) < 2:
            return ()

        achievement = ACHIEVEMENTS["THROWING_HABIT_1"]
        ability = ABILITIES["STEADY_HAND"]
        evidence = {
            "successful_throw_count": len(projectile_ids),
            "projectile_ids": distinct_projectiles,
        }
        inserted = conn.execute(
            """
            INSERT OR IGNORE INTO player_achievements(
                player_actor_id, achievement_code, unlocked_at, trigger_event_id, evidence_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                player_id,
                achievement.code,
                now_text,
                event_id,
                json.dumps(evidence, ensure_ascii=False, sort_keys=True),
            ),
        ).rowcount
        if not inserted:
            return ()

        conn.execute(
            """
            INSERT OR IGNORE INTO player_abilities(
                player_actor_id, ability_code, unlocked_at, source_achievement_code
            ) VALUES (?, ?, ?, ?)
            """,
            (player_id, ability.code, now_text, achievement.code),
        )
        return (
            ProgressionUnlock("achievement", achievement.code, achievement.name),
            ProgressionUnlock("ability", ability.code, ability.name),
        )
