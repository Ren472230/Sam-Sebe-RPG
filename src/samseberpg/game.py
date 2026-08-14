from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5

from .clock import Clock
from .db import START_LOCATION_ID, WORLD_ID, GameDatabase, to_utc_text
from .domain import ActionResult, ActionType, CanonicalAction, VisibleActor, VisibleEntity, WorldView
from .world import WorldSynchronizer


class GameService:
    def __init__(self, db: GameDatabase, clock: Clock):
        self.db = db
        self.clock = clock
        self.synchronizer = WorldSynchronizer()

    def register_player(self, discord_user_id: str, name: str) -> str:
        if not discord_user_id.strip():
            raise ValueError("discord_user_id must not be empty")
        if not name.strip():
            raise ValueError("name must not be empty")
        now = to_utc_text(self.clock.now())
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT actor_id FROM players WHERE discord_user_id = ?",
                    (discord_user_id,),
                ).fetchone()
                if existing:
                    conn.commit()
                    return existing["actor_id"]
                actor_id = f"player_{uuid5(NAMESPACE_URL, 'sam-sebe-rpg:' + discord_user_id).hex[:16]}"
                conn.execute(
                    "INSERT INTO actors(id, world_id, actor_type, name, location_id, created_at) VALUES (?, ?, 'player', ?, ?, ?)",
                    (actor_id, WORLD_ID, name.strip(), START_LOCATION_ID, now),
                )
                conn.execute(
                    "INSERT INTO players(actor_id, discord_user_id, joined_at, coins) VALUES (?, ?, ?, 10)",
                    (actor_id, discord_user_id, now),
                )
                conn.commit()
                return actor_id
            except Exception:
                conn.rollback()
                raise

    def execute(self, action: CanonicalAction, external_id: str | None = None) -> ActionResult:
        now_text = to_utc_text(self.clock.now())
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if external_id is not None:
                    replay = conn.execute(
                        "SELECT result_json FROM processed_interactions WHERE external_id = ?",
                        (external_id,),
                    ).fetchone()
                    if replay is not None:
                        payload = json.loads(replay["result_json"])
                        conn.commit()
                        return ActionResult(
                            success=bool(payload["success"]),
                            code=payload["code"],
                            summary=payload["summary"],
                            event_id=payload["event_id"],
                            data=payload.get("data", {}),
                            replayed=True,
                        )

                self.synchronizer.catch_up(conn, WORLD_ID, self.clock.now())
                actor = conn.execute(
                    "SELECT id, world_id, location_id FROM actors WHERE id = ? AND actor_type = 'player'",
                    (action.actor_id,),
                ).fetchone()
                if actor is None:
                    result = ActionResult(False, "PLAYER_NOT_FOUND", "Игрок не найден.")
                    event_id = self._append_event(conn, action, result, external_id, now_text, None)
                    final = ActionResult(False, result.code, result.summary, event_id=event_id)
                    self._store_interaction(conn, external_id, action.actor_id, final, now_text)
                    conn.commit()
                    return final

                if action.action_type == ActionType.LOOK:
                    result = ActionResult(True, "OK", "Вы осматриваетесь.", data={"location_id": actor["location_id"]})
                elif action.action_type == ActionType.MOVE:
                    result = self._move(conn, action, actor["location_id"])
                elif action.action_type == ActionType.TAKE:
                    result = self._take(conn, action, actor["location_id"])
                elif action.action_type == ActionType.DROP:
                    result = self._drop(conn, action, actor["location_id"])
                else:
                    raise ValueError(f"unsupported action type: {action.action_type}")

                current_location = conn.execute(
                    "SELECT location_id FROM actors WHERE id = ?", (action.actor_id,)
                ).fetchone()["location_id"]
                event_id = self._append_event(conn, action, result, external_id, now_text, current_location)
                final = ActionResult(
                    success=result.success,
                    code=result.code,
                    summary=result.summary,
                    event_id=event_id,
                    data=result.data,
                )
                self._store_interaction(conn, external_id, action.actor_id, final, now_text)
                conn.commit()
                return final
            except Exception:
                conn.rollback()
                raise

    def _move(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        destination = action.destination_id
        if destination is None:
            return ActionResult(False, "INVALID_DESTINATION", "Не указано, куда идти.")
        edge = conn.execute(
            "SELECT 1 FROM location_edges WHERE world_id = ? AND from_location_id = ? AND to_location_id = ?",
            (WORLD_ID, location_id, destination),
        ).fetchone()
        if edge is None:
            return ActionResult(False, "INVALID_DESTINATION", "Отсюда туда нельзя пройти напрямую.")
        conn.execute("UPDATE actors SET location_id = ? WHERE id = ?", (destination, action.actor_id))
        return ActionResult(True, "OK", f"Вы переходите в {destination}.", data={"location_id": destination})

    def _take(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        if action.target_id is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Не указано, что взять.")
        entity = conn.execute(
            "SELECT id, name, location_id, owner_actor_id, portable FROM entities WHERE id = ?",
            (action.target_id,),
        ).fetchone()
        if entity is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такого объекта нет.")
        if entity["owner_actor_id"] is not None:
            return ActionResult(False, "ALREADY_OWNED", "Этот предмет уже у кого-то.")
        if entity["location_id"] != location_id:
            return ActionResult(False, "TARGET_NOT_PRESENT", "Этого предмета здесь нет.")
        if not entity["portable"]:
            return ActionResult(False, "NOT_PORTABLE", "Этот объект нельзя поднять.")
        conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = ? WHERE id = ?",
            (action.actor_id, action.target_id),
        )
        return ActionResult(True, "OK", f"Вы берёте {entity['name']}.", data={"entity_id": action.target_id})

    def _drop(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        if action.target_id is None:
            return ActionResult(False, "ITEM_NOT_OWNED", "Не указано, что положить.")
        entity = conn.execute(
            "SELECT id, name, owner_actor_id FROM entities WHERE id = ?", (action.target_id,)
        ).fetchone()
        if entity is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такого предмета нет.")
        if entity["owner_actor_id"] != action.actor_id:
            return ActionResult(False, "ITEM_NOT_OWNED", "У вас нет этого предмета.")
        conn.execute(
            "UPDATE entities SET owner_actor_id = NULL, location_id = ? WHERE id = ?",
            (location_id, action.target_id),
        )
        return ActionResult(True, "OK", f"Вы кладёте {entity['name']}.", data={"entity_id": action.target_id})

    @staticmethod
    def _store_interaction(conn, external_id: str | None, actor_id: str, result: ActionResult, now_text: str) -> None:
        if external_id is None:
            return
        payload = json.dumps(
            {
                "success": result.success,
                "code": result.code,
                "summary": result.summary,
                "event_id": result.event_id,
                "data": result.data,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            "INSERT INTO processed_interactions(external_id, world_id, actor_id, action_event_id, result_json, processed_at) VALUES (?, ?, ?, ?, ?, ?)",
            (external_id, WORLD_ID, actor_id, result.event_id, payload, now_text),
        )

    @staticmethod
    def _append_event(conn, action: CanonicalAction, result: ActionResult, external_id: str | None, now_text: str, location_id: str | None) -> int:
        cursor = conn.execute(
            """
            INSERT INTO action_events(
                world_id, external_id, occurred_at, actor_id, action_type,
                target_id, location_id, success, result_code, summary, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}')
            """,
            (
                WORLD_ID,
                external_id,
                now_text,
                action.actor_id,
                action.action_type.value,
                action.target_id,
                location_id,
                int(result.success),
                result.code,
                result.summary,
            ),
        )
        return int(cursor.lastrowid)

    def observe(self, player_id: str) -> WorldView:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self.synchronizer.catch_up(conn, WORLD_ID, self.clock.now())
                player = conn.execute(
                    """
                    SELECT a.id, a.location_id, l.name AS location_name, l.description
                    FROM actors a
                    JOIN players p ON p.actor_id = a.id
                    JOIN locations l ON l.id = a.location_id
                    WHERE a.id = ?
                    """,
                    (player_id,),
                ).fetchone()
                if player is None:
                    raise KeyError(f"unknown player: {player_id}")
                actor_rows = conn.execute(
                    """
                    SELECT a.id, a.name, a.actor_type, n.current_activity
                    FROM actors a
                    LEFT JOIN npcs n ON n.actor_id = a.id
                    WHERE a.location_id = ? AND a.id != ?
                    ORDER BY a.actor_type, a.name, a.id
                    """,
                    (player["location_id"], player_id),
                ).fetchall()
                entity_rows = conn.execute(
                    "SELECT id, name, entity_type, portable FROM entities WHERE location_id = ? ORDER BY id",
                    (player["location_id"],),
                ).fetchall()
                inventory_rows = conn.execute(
                    "SELECT id, name, entity_type, portable FROM entities WHERE owner_actor_id = ? ORDER BY id",
                    (player_id,),
                ).fetchall()
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return WorldView(
            player_id=player_id,
            location_id=player["location_id"],
            location_name=player["location_name"],
            location_description=player["description"],
            actors=tuple(
                VisibleActor(id=row["id"], name=row["name"], actor_type=row["actor_type"], activity=row["current_activity"])
                for row in actor_rows
            ),
            entities=tuple(
                VisibleEntity(id=row["id"], name=row["name"], entity_type=row["entity_type"], portable=bool(row["portable"]))
                for row in entity_rows
            ),
            inventory=tuple(
                VisibleEntity(id=row["id"], name=row["name"], entity_type=row["entity_type"], portable=bool(row["portable"]))
                for row in inventory_rows
            ),
        )
