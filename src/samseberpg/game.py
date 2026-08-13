from __future__ import annotations

import json
import random
import sqlite3
from typing import Any

from .db import GameDatabase
from .domain import ActionResult, ActionType, CanonicalAction


class GameService:
    def __init__(self, db: GameDatabase, seed: int = 0):
        self.db = db
        self.rng = random.Random(seed)

    def execute(self, action: CanonicalAction) -> ActionResult:
        with self.db.connect() as connection:
            player = connection.execute(
                "SELECT * FROM player_state WHERE player_id = ?", (action.actor_id,)
            ).fetchone()
            if player is None:
                result = self._finish(
                    connection,
                    action,
                    location_id=None,
                    success=False,
                    code="PLAYER_NOT_FOUND",
                    summary="Игрок не найден.",
                )
            else:
                location_id = player["location_id"]
                if action.action_type is ActionType.LOOK:
                    result = self._look(connection, action, location_id)
                elif action.action_type is ActionType.TAKE:
                    result = self._take(connection, action, location_id)
                elif action.action_type is ActionType.DROP:
                    result = self._drop(connection, action, location_id)
                elif action.action_type is ActionType.MOVE:
                    result = self._move(connection, action, location_id)
                elif action.action_type is ActionType.WAIT:
                    result = self._wait(connection, action, location_id)
                elif action.action_type is ActionType.THROW:
                    result = self._throw(connection, action, location_id)
                else:
                    result = self._finish(
                        connection,
                        action,
                        location_id=location_id,
                        success=False,
                        code="ACTION_NOT_IMPLEMENTED",
                        summary="Это действие пока недоступно.",
                    )

        if action.action_type is ActionType.THROW and result.success:
            from .progression import ProgressionService

            unlocked = ProgressionService(self.db).evaluate(action.actor_id)
            if unlocked:
                data = dict(result.data)
                data["unlocked"] = unlocked
                result = ActionResult(
                    success=result.success,
                    code=result.code,
                    summary=result.summary,
                    data=data,
                )

        return result

    def _take(
        self, connection: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        item = (
            connection.execute(
                "SELECT * FROM entities WHERE entity_id = ?", (action.item_id,)
            ).fetchone()
            if action.item_id
            else None
        )
        if item is None or item["entity_type"] != "item" or item["location_id"] != location_id:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="ITEM_NOT_PRESENT",
                summary="Здесь нет такого предмета.",
            )

        connection.execute(
            "INSERT INTO inventory(player_id, item_id) VALUES (?, ?)",
            (action.actor_id, action.item_id),
        )
        connection.execute(
            "UPDATE entities SET location_id = NULL WHERE entity_id = ?",
            (action.item_id,),
        )
        return self._finish(
            connection,
            action,
            location_id=location_id,
            success=True,
            code="OK",
            summary=f"Вы берёте {item['name']}.",
        )

    def _throw(
        self, connection: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        owned = (
            connection.execute(
                "SELECT 1 FROM inventory WHERE player_id = ? AND item_id = ?",
                (action.actor_id, action.item_id),
            ).fetchone()
            if action.item_id
            else None
        )
        if owned is None:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="ITEM_NOT_OWNED",
                summary="Сначала нужно завладеть предметом.",
            )

        item = connection.execute(
            "SELECT * FROM entities WHERE entity_id = ?", (action.item_id,)
        ).fetchone()
        tags = json.loads(item["tags_json"]) if item else []
        if "improvised_projectile" not in tags:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="ITEM_NOT_THROWABLE",
                summary="Этот предмет не подходит для броска.",
            )

        target = (
            connection.execute(
                "SELECT * FROM entities WHERE entity_id = ?", (action.target_id,)
            ).fetchone()
            if action.target_id
            else None
        )
        if target is None or target["location_id"] != location_id:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="TARGET_NOT_PRESENT",
                summary="Цели здесь нет.",
            )

        aimed = bool(action.modifiers.get("aimed", False))
        if aimed:
            ability = connection.execute(
                "SELECT 1 FROM abilities WHERE player_id = ? AND ability_id = ?",
                (action.actor_id, "aimed_throw"),
            ).fetchone()
            if ability is None:
                return self._finish(
                    connection,
                    action,
                    location_id=location_id,
                    success=False,
                    code="ACTION_NOT_UNLOCKED",
                    summary="Вы ещё не умеете выполнять прицельный бросок.",
                )

        accuracy_chance = 0.55 if aimed else 0.45
        accuracy_roll = self.rng.random()
        hit = accuracy_roll < accuracy_chance

        connection.execute(
            "DELETE FROM inventory WHERE player_id = ? AND item_id = ?",
            (action.actor_id, action.item_id),
        )
        connection.execute(
            "UPDATE entities SET location_id = ? WHERE entity_id = ?",
            (location_id, action.item_id),
        )
        evidence = {
            "hit": hit,
            "accuracy_roll": accuracy_roll,
            "accuracy_chance": accuracy_chance,
            "item_kind": item["item_kind"],
            "aimed": aimed,
        }
        summary = (
            f"{item['name']} попадает в цель: {target['name']}."
            if hit
            else f"{item['name']} пролетает мимо цели: {target['name']}."
        )
        return self._finish(
            connection,
            action,
            location_id=location_id,
            success=True,
            code="OK",
            summary=summary,
            behavior_tags=("throw",),
            evidence=evidence,
            data=evidence,
        )

    def _look(
        self, connection: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        location = connection.execute(
            "SELECT name FROM entities WHERE entity_id = ? AND entity_type = 'location'",
            (location_id,),
        ).fetchone()
        rows = connection.execute(
            """
            SELECT entity_id, entity_type, name, item_kind, tags_json
            FROM entities
            WHERE location_id = ?
            ORDER BY entity_type, entity_id
            """,
            (location_id,),
        ).fetchall()
        entities = [
            {
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "name": row["name"],
                "item_kind": row["item_kind"],
                "tags": json.loads(row["tags_json"]),
            }
            for row in rows
        ]
        return self._finish(
            connection,
            action,
            location_id=location_id,
            success=True,
            code="OK",
            summary=f"Вы осматриваете {location['name'] if location else location_id}.",
            data={"location_id": location_id, "entities": entities},
        )

    def _wait(
        self, connection: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        ticks = action.modifiers.get("ticks", 1)
        if not isinstance(ticks, int) or isinstance(ticks, bool) or ticks < 1:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="INVALID_WAIT",
                summary="Нужно указать положительное число тактов.",
            )
        current = connection.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        world_time = int(current["value"]) if current else 0
        connection.execute(
            "INSERT OR REPLACE INTO world_meta(key, value) VALUES ('world_time', ?)",
            (str(world_time + ticks),),
        )
        return self._finish(
            connection,
            action,
            location_id=location_id,
            success=True,
            code="OK",
            summary=f"Проходит {ticks} такт.",
            data={"world_time": world_time + ticks},
        )

    def _move(
        self, connection: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        current = connection.execute(
            "SELECT * FROM entities WHERE entity_id = ? AND entity_type = 'location'",
            (location_id,),
        ).fetchone()
        destination = (
            connection.execute(
                "SELECT * FROM entities WHERE entity_id = ? AND entity_type = 'location'",
                (action.destination_id,),
            ).fetchone()
            if action.destination_id
            else None
        )
        connections = json.loads(current["state_json"]).get("connections", []) if current else []
        if destination is None or action.destination_id not in connections:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="INVALID_DESTINATION",
                summary="Отсюда туда пройти нельзя.",
            )

        connection.execute(
            "UPDATE player_state SET location_id = ? WHERE player_id = ?",
            (action.destination_id, action.actor_id),
        )
        return self._finish(
            connection,
            action,
            location_id=action.destination_id,
            success=True,
            code="OK",
            summary=f"Вы переходите: {destination['name']}.",
            data={"location_id": action.destination_id},
        )

    def _drop(
        self, connection: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        owned = (
            connection.execute(
                "SELECT 1 FROM inventory WHERE player_id = ? AND item_id = ?",
                (action.actor_id, action.item_id),
            ).fetchone()
            if action.item_id
            else None
        )
        if owned is None:
            return self._finish(
                connection,
                action,
                location_id=location_id,
                success=False,
                code="ITEM_NOT_OWNED",
                summary="У вас нет такого предмета.",
            )

        item = connection.execute(
            "SELECT name FROM entities WHERE entity_id = ?", (action.item_id,)
        ).fetchone()
        connection.execute(
            "DELETE FROM inventory WHERE player_id = ? AND item_id = ?",
            (action.actor_id, action.item_id),
        )
        connection.execute(
            "UPDATE entities SET location_id = ? WHERE entity_id = ?",
            (location_id, action.item_id),
        )
        return self._finish(
            connection,
            action,
            location_id=location_id,
            success=True,
            code="OK",
            summary=f"Вы оставляете {item['name']} здесь.",
        )

    def _finish(
        self,
        connection: sqlite3.Connection,
        action: CanonicalAction,
        *,
        location_id: str | None,
        success: bool,
        code: str,
        summary: str,
        behavior_tags: tuple[str, ...] = (),
        evidence: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ActionResult:
        row = connection.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        world_time = int(row["value"]) if row else 0
        connection.execute(
            """
            INSERT INTO action_events(
                world_time, actor_id, action_type, target_id, item_id, location_id,
                success, result_code, behavior_tags_json, evidence_json, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                world_time,
                action.actor_id,
                action.action_type.value,
                action.target_id,
                action.item_id,
                location_id,
                int(success),
                code,
                json.dumps(list(behavior_tags), ensure_ascii=False),
                json.dumps(evidence or {}, ensure_ascii=False),
                summary,
            ),
        )
        return ActionResult(success=success, code=code, summary=summary, data=data or {})
