from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from .db import GameDatabase
from .domain import ActionResult, ActionType, CanonicalAction
from .world import LOCATION_GRAPH
from .progression import ProgressionService


class GameService:
    def __init__(self, db: GameDatabase, seed: int = 0):
        self.db = db
        self.rng = random.Random(seed)

    def execute(self, action: CanonicalAction) -> ActionResult:
        with self.db.connect() as conn:
            player = conn.execute(
                "SELECT player_id, location_id FROM player_state WHERE player_id = ?",
                (action.actor_id,),
            ).fetchone()
            if player is None:
                return self._record(
                    conn, action, None, False, "PLAYER_NOT_FOUND", "Игрок не найден."
                )

            location_id = player["location_id"]
            if action.action_type == ActionType.LOOK:
                return self._look(conn, action, location_id)
            if action.action_type == ActionType.MOVE:
                return self._move(conn, action, location_id)
            if action.action_type == ActionType.TAKE:
                return self._take(conn, action, location_id)
            if action.action_type == ActionType.DROP:
                return self._drop(conn, action, location_id)
            if action.action_type == ActionType.THROW:
                return self._throw(conn, action, location_id)
            if action.action_type == ActionType.WAIT:
                return self._wait(conn, action, location_id)
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ACTION_NOT_IMPLEMENTED",
                "Это действие пока недоступно.",
            )

    def _look(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        entities = conn.execute(
            """
            SELECT entity_id, entity_type, name
            FROM entities
            WHERE location_id = ?
            ORDER BY entity_type, entity_id
            """,
            (location_id,),
        ).fetchall()
        data = {
            "location_id": location_id,
            "entities": [dict(row) for row in entities],
        }
        return self._record(
            conn, action, location_id, True, "OK", "Ты осматриваешься.", data=data
        )

    def _move(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        destination = action.destination_id
        if destination not in LOCATION_GRAPH.get(location_id, set()):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "INVALID_DESTINATION",
                "Отсюда туда нельзя пройти напрямую.",
            )
        conn.execute(
            "UPDATE player_state SET location_id = ? WHERE player_id = ?",
            (destination, action.actor_id),
        )
        return self._record(
            conn,
            action,
            destination,
            True,
            "OK",
            f"Ты переходишь в {destination}.",
        )

    def _take(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        if not action.item_id:
            return self._record(
                conn, action, location_id, False, "ITEM_REQUIRED", "Нужно указать предмет."
            )
        item = conn.execute(
            "SELECT entity_type, location_id FROM entities WHERE entity_id = ?",
            (action.item_id,),
        ).fetchone()
        if item is None or item["entity_type"] != "item" or item["location_id"] != location_id:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_PRESENT",
                "Этого предмета здесь нет.",
            )
        conn.execute(
            "INSERT INTO inventory(player_id, item_id) VALUES (?, ?)",
            (action.actor_id, action.item_id),
        )
        conn.execute(
            "UPDATE entities SET location_id = NULL WHERE entity_id = ?",
            (action.item_id,),
        )
        return self._record(
            conn, action, location_id, True, "OK", f"Ты берёшь {action.item_id}."
        )

    def _drop(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        if not action.item_id:
            return self._record(
                conn, action, location_id, False, "ITEM_REQUIRED", "Нужно указать предмет."
            )
        owned = conn.execute(
            "SELECT 1 FROM inventory WHERE player_id = ? AND item_id = ?",
            (action.actor_id, action.item_id),
        ).fetchone()
        if owned is None:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_OWNED",
                "Этого предмета нет в инвентаре.",
            )
        conn.execute(
            "DELETE FROM inventory WHERE player_id = ? AND item_id = ?",
            (action.actor_id, action.item_id),
        )
        conn.execute(
            "UPDATE entities SET location_id = ? WHERE entity_id = ?",
            (location_id, action.item_id),
        )
        return self._record(
            conn, action, location_id, True, "OK", f"Ты оставляешь {action.item_id}."
        )

    def _throw(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        if not action.item_id:
            return self._record(
                conn, action, location_id, False, "ITEM_REQUIRED", "Нужно указать предмет."
            )
        if not action.target_id:
            return self._record(
                conn, action, location_id, False, "TARGET_REQUIRED", "Нужно указать цель."
            )

        owned = conn.execute(
            "SELECT 1 FROM inventory WHERE player_id = ? AND item_id = ?",
            (action.actor_id, action.item_id),
        ).fetchone()
        if owned is None:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_OWNED",
                "Этого предмета нет в инвентаре.",
            )

        item = conn.execute(
            "SELECT tags_json FROM entities WHERE entity_id = ?",
            (action.item_id,),
        ).fetchone()
        tags = json.loads(item["tags_json"]) if item else []
        if "improvised_projectile" not in tags:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_THROWABLE",
                "Этот предмет не подходит для броска в пилоте.",
            )

        target = conn.execute(
            "SELECT entity_id FROM entities WHERE entity_id = ? AND location_id = ?",
            (action.target_id, location_id),
        ).fetchone()
        if target is None:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "TARGET_NOT_PRESENT",
                "Этой цели здесь нет.",
            )

        aimed = bool(action.modifiers.get("aimed", False))
        if aimed:
            unlocked = conn.execute(
                "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = 'aimed_throw'",
                (action.actor_id,),
            ).fetchone()
            if unlocked is None:
                return self._record(
                    conn,
                    action,
                    location_id,
                    False,
                    "ACTION_NOT_UNLOCKED",
                    "Точный бросок ещё не освоен.",
                )

        roll = self.rng.random()
        chance = 0.55 if aimed else 0.45
        hit = roll < chance
        projectile_types = [tag for tag in tags if tag != "improvised_projectile"]
        projectile_type = projectile_types[0] if projectile_types else "unknown"

        conn.execute(
            "DELETE FROM inventory WHERE player_id = ? AND item_id = ?",
            (action.actor_id, action.item_id),
        )
        conn.execute(
            "UPDATE entities SET location_id = ? WHERE entity_id = ?",
            (location_id, action.item_id),
        )

        summary = (
            f"{action.item_id} попадает в {action.target_id}."
            if hit
            else f"{action.item_id} пролетает мимо {action.target_id}."
        )
        result = self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            summary,
            behavior_tags=["throwing", "improvised_projectile"],
            evidence={
                "hit": hit,
                "accuracy_roll": roll,
                "base_accuracy": chance,
                "projectile_type": projectile_type,
                "target_id": action.target_id,
                "location_id": location_id,
                "aimed": aimed,
            },
            data={"hit": hit, "accuracy_roll": roll, "accuracy": chance},
        )
        ProgressionService(self.db).evaluate(action.actor_id, conn)
        return result

    def _wait(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        try:
            ticks = int(action.modifiers.get("ticks", 1))
        except (TypeError, ValueError):
            ticks = 0
        if ticks < 1 or ticks > 100:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "INVALID_WAIT",
                "Ожидание должно быть от 1 до 100 тактов.",
            )
        current = self._world_time(conn)
        new_time = current + ticks
        conn.execute(
            "UPDATE world_meta SET value = ? WHERE key = 'world_time'",
            (str(new_time),),
        )
        return self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            f"Проходит {ticks} такт(а/ов).",
            data={"world_time": new_time},
        )

    def _world_time(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def _record(
        self,
        conn: sqlite3.Connection,
        action: CanonicalAction,
        location_id: str | None,
        success: bool,
        code: str,
        summary: str,
        *,
        behavior_tags: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ActionResult:
        conn.execute(
            """
            INSERT INTO action_events(
                world_time, actor_id, action_type, target_id, item_id, location_id,
                success, result_code, behavior_tags_json, evidence_json, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._world_time(conn),
                action.actor_id,
                action.action_type.value,
                action.target_id,
                action.item_id,
                location_id,
                int(success),
                code,
                json.dumps(behavior_tags or []),
                json.dumps(evidence or {}),
                summary,
            ),
        )
        return ActionResult(success=success, code=code, summary=summary, data=data or {})
