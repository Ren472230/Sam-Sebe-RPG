from __future__ import annotations

import json
import sqlite3
from typing import Any


class LivingWorldService:
    def tick(
        self, conn: sqlite3.Connection, world_time: int
    ) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        event = self._tick_mira(conn, world_time)
        if event is not None:
            events.append(event)
        event = self._tick_kaspar(conn, world_time)
        if event is not None:
            events.append(event)
        return events

    def _tick_mira(
        self, conn: sqlite3.Connection, world_time: int
    ) -> dict[str, object] | None:
        row = conn.execute(
            "SELECT location_id, state_json FROM entities WHERE entity_id = 'mira_craftswoman'"
        ).fetchone()
        if row is None:
            return None

        state = json.loads(row["state_json"])
        wood_stock = int(state.get("wood_stock", 0))
        requested = bool(state.get("requested_wood", False))

        if wood_stock > 0 and world_time % 2 == 0:
            state["wood_stock"] = wood_stock - 1
            state["work_cycles"] = int(state.get("work_cycles", 0)) + 1
            self._save_state(conn, "mira_craftswoman", state)
            return self._record_event(
                conn,
                world_time=world_time,
                actor_id="mira_craftswoman",
                event_type="NPC_WORKED",
                location_id=row["location_id"],
                data={"wood_stock": state["wood_stock"], "work_cycles": state["work_cycles"]},
                summary="Мира расходует древесину на работу в мастерской.",
            )

        if wood_stock == 0 and not requested:
            state["requested_wood"] = True
            self._save_state(conn, "mira_craftswoman", state)
            return self._record_event(
                conn,
                world_time=world_time,
                actor_id="mira_craftswoman",
                event_type="NPC_REQUESTED_RESOURCE",
                target_id="kaspar_forager",
                location_id=row["location_id"],
                data={"resource": "useful_wood"},
                summary="У Миры заканчивается древесина, и она просит Каспара найти материал.",
            )

        return None

    def _tick_kaspar(
        self, conn: sqlite3.Connection, world_time: int
    ) -> dict[str, object] | None:
        kaspar_row = conn.execute(
            "SELECT location_id, state_json FROM entities WHERE entity_id = 'kaspar_forager'"
        ).fetchone()
        mira_row = conn.execute(
            "SELECT location_id, state_json FROM entities WHERE entity_id = 'mira_craftswoman'"
        ).fetchone()
        if kaspar_row is None or mira_row is None:
            return None

        kaspar_state = json.loads(kaspar_row["state_json"])
        mira_state = json.loads(mira_row["state_json"])
        carrying = int(kaspar_state.get("carrying_wood", 0))
        kaspar_location = kaspar_row["location_id"]
        mira_location = mira_row["location_id"]

        if carrying > 0:
            if kaspar_location == mira_location:
                mira_state["wood_stock"] = int(mira_state.get("wood_stock", 0)) + carrying
                mira_state["requested_wood"] = False
                kaspar_state["carrying_wood"] = 0
                self._save_state(conn, "mira_craftswoman", mira_state)
                self._save_state(conn, "kaspar_forager", kaspar_state)
                return self._record_event(
                    conn,
                    world_time=world_time,
                    actor_id="kaspar_forager",
                    event_type="NPC_DELIVERED_RESOURCE",
                    target_id="mira_craftswoman",
                    location_id=kaspar_location,
                    data={"resource_id": "driftwood_1", "amount": carrying},
                    summary="Каспар приносит Мире найденную древесину.",
                )

            next_location = self._next_hop(kaspar_location, mira_location)
            if next_location is None:
                return None
            conn.execute(
                "UPDATE entities SET location_id = ? WHERE entity_id = 'kaspar_forager'",
                (next_location,),
            )
            return self._record_event(
                conn,
                world_time=world_time,
                actor_id="kaspar_forager",
                event_type="NPC_MOVED",
                target_id="mira_craftswoman",
                location_id=next_location,
                data={"from": kaspar_location, "to": next_location, "purpose": "deliver_wood"},
                summary="Каспар несёт древесину обратно к Мире.",
            )

        if not bool(mira_state.get("requested_wood", False)):
            return None

        if kaspar_location != "river_edge":
            next_location = self._next_hop(kaspar_location, "river_edge")
            if next_location is None:
                return None
            conn.execute(
                "UPDATE entities SET location_id = ? WHERE entity_id = 'kaspar_forager'",
                (next_location,),
            )
            return self._record_event(
                conn,
                world_time=world_time,
                actor_id="kaspar_forager",
                event_type="NPC_MOVED",
                target_id="river_edge",
                location_id=next_location,
                data={"from": kaspar_location, "to": next_location, "purpose": "collect_wood"},
                summary="Каспар идёт к реке искать древесину для Миры.",
            )

        resource = conn.execute(
            "SELECT location_id FROM entities WHERE entity_id = 'driftwood_1'"
        ).fetchone()
        if resource is None or resource["location_id"] != "river_edge":
            return None

        conn.execute(
            "UPDATE entities SET location_id = NULL WHERE entity_id = 'driftwood_1'"
        )
        kaspar_state["carrying_wood"] = 1
        self._save_state(conn, "kaspar_forager", kaspar_state)
        return self._record_event(
            conn,
            world_time=world_time,
            actor_id="kaspar_forager",
            event_type="NPC_COLLECTED_RESOURCE",
            target_id="driftwood_1",
            location_id="river_edge",
            data={"resource_id": "driftwood_1", "resource": "useful_wood"},
            summary="Каспар подбирает у реки подходящую древесину.",
        )

    def _next_hop(self, current: str | None, target: str | None) -> str | None:
        if current is None or target is None or current == target:
            return None
        if current == "village_square":
            if target in {"workshop_yard", "river_edge"}:
                return target
            return None
        if target == "village_square":
            return "village_square"
        if {current, target} == {"workshop_yard", "river_edge"}:
            return "village_square"
        return None

    def _save_state(
        self, conn: sqlite3.Connection, entity_id: str, state: dict[str, Any]
    ) -> None:
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE entity_id = ?",
            (json.dumps(state, ensure_ascii=False), entity_id),
        )

    def _record_event(
        self,
        conn: sqlite3.Connection,
        *,
        world_time: int,
        actor_id: str,
        event_type: str,
        target_id: str | None = None,
        location_id: str | None = None,
        data: dict[str, Any] | None = None,
        summary: str,
    ) -> dict[str, object]:
        payload = data or {}
        cursor = conn.execute(
            """
            INSERT INTO world_events(
                world_time, actor_id, event_type, target_id, location_id, data_json, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                world_time,
                actor_id,
                event_type,
                target_id,
                location_id,
                json.dumps(payload, ensure_ascii=False),
                summary,
            ),
        )
        return {
            "event_id": int(cursor.lastrowid),
            "world_time": world_time,
            "actor_id": actor_id,
            "event_type": event_type,
            "target_id": target_id,
            "location_id": location_id,
            "data": payload,
            "summary": summary,
        }
