from __future__ import annotations

from collections import deque
import json
import sqlite3

from samseberpg.db import DEFAULT_WORLD_ID


_ALLOWED_EVENT_TYPES = {
    "NPC_WORKED",
    "NPC_REQUESTED_RESOURCE",
    "NPC_MOVED",
    "NPC_COLLECTED_RESOURCE",
    "NPC_DELIVERED_RESOURCE",
}


class LivingWorldService:
    def advance(self, conn: sqlite3.Connection, ticks: int) -> list[dict[str, object]]:
        if isinstance(ticks, bool) or not isinstance(ticks, int) or not 1 <= ticks <= 60:
            raise ValueError("ticks must be an integer from 1 to 60")

        events: list[dict[str, object]] = []
        for _ in range(ticks):
            cursor = conn.execute(
                "UPDATE world_runtime SET tick = tick + 1 WHERE world_id = ?",
                (DEFAULT_WORLD_ID,),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"missing world runtime for {DEFAULT_WORLD_ID}")
            tick = int(
                conn.execute(
                    "SELECT tick FROM world_runtime WHERE world_id = ?",
                    (DEFAULT_WORLD_ID,),
                ).fetchone()[0]
            )

            mira_event = self._advance_mira(conn, tick)
            if mira_event is not None:
                events.append(mira_event)

            kaspar_event = self._advance_kaspar(conn, tick)
            if kaspar_event is not None:
                events.append(kaspar_event)

        return events

    def give_resource(
        self,
        conn: sqlite3.Connection,
        *,
        player_id: str,
        entity_id: str,
        recipient_id: str,
    ) -> tuple[bool, str, str]:
        if recipient_id != "npc_mira":
            return False, "UNSUPPORTED_RECIPIENT", "This resource request belongs to Mira."
        if entity_id != "driftwood_1":
            return False, "UNSUPPORTED_RESOURCE", "Mira needs the useful driftwood resource."

        entity = conn.execute(
            "SELECT owner_actor_id, state_json FROM entities WHERE id = ?",
            (entity_id,),
        ).fetchone()
        if entity is None or entity["owner_actor_id"] != player_id:
            return False, "ITEM_NOT_OWNED", "Item is not owned by this player."
        resource_state = json.loads(str(entity["state_json"]))
        if not isinstance(resource_state, dict) or resource_state.get("resource_kind") != "useful_wood":
            return False, "UNSUPPORTED_RESOURCE", "Mira needs useful wood."

        _, mira_state = self._load_runtime(conn, "npc_mira")
        if not bool(mira_state.get("requested_wood", False)):
            return False, "RESOURCE_NOT_NEEDED", "Mira is not requesting wood right now."

        _, kaspar_state = self._load_runtime(conn, "npc_kaspar")
        if self._state_int(kaspar_state, "carrying_wood") != 0:
            return False, "RESOURCE_UNAVAILABLE", "Kaspar is already carrying the requested wood."

        tick_row = conn.execute(
            "SELECT tick FROM world_runtime WHERE world_id = ?",
            (DEFAULT_WORLD_ID,),
        ).fetchone()
        if tick_row is None:
            raise RuntimeError(f"missing world runtime for {DEFAULT_WORLD_ID}")
        tick = int(tick_row[0])

        consumed = conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = NULL "
            "WHERE id = ? AND owner_actor_id = ?",
            (entity_id, player_id),
        )
        if consumed.rowcount != 1:
            return False, "ITEM_NOT_OWNED", "Item is not owned by this player."

        mira_state["wood_stock"] = self._state_int(mira_state, "wood_stock") + 1
        mira_state["requested_wood"] = False
        self._save_runtime(
            conn,
            "npc_mira",
            override_active=0,
            state=mira_state,
            tick=tick,
        )

        kaspar_state["carrying_wood"] = 0
        kaspar_state["goal"] = None
        self._save_runtime(
            conn,
            "npc_kaspar",
            override_active=0,
            state=kaspar_state,
            tick=tick,
        )
        return True, "OK", "Gave driftwood_1 to Mira and satisfied her wood request."

    def _advance_mira(
        self, conn: sqlite3.Connection, tick: int
    ) -> dict[str, object] | None:
        override_active, state = self._load_runtime(conn, "npc_mira")
        wood_stock = self._state_int(state, "wood_stock")
        work_cycles = self._state_int(state, "work_cycles")
        requested_wood = bool(state.get("requested_wood", False))

        if tick % 2 == 0 and wood_stock > 0:
            wood_stock -= 1
            work_cycles += 1
            state["wood_stock"] = wood_stock
            state["work_cycles"] = work_cycles
            state["requested_wood"] = requested_wood
            self._save_runtime(
                conn,
                "npc_mira",
                override_active=override_active,
                state=state,
                tick=tick,
            )
            location_id = self._actor_location(conn, "npc_mira")
            return self._record_event(
                conn,
                tick=tick,
                actor_id="npc_mira",
                event_type="NPC_WORKED",
                target_id=None,
                location_id=location_id,
                data={"wood_stock": wood_stock, "work_cycles": work_cycles},
                summary="Mira completed one workshop work cycle.",
            )

        if wood_stock == 0 and not requested_wood:
            state["requested_wood"] = True
            state["wood_stock"] = wood_stock
            state["work_cycles"] = work_cycles
            conn.execute(
                "UPDATE actors SET location_id = 'workshop_yard' WHERE id = 'npc_mira'"
            )
            self._save_runtime(
                conn,
                "npc_mira",
                override_active=1,
                state=state,
                tick=tick,
            )
            return self._record_event(
                conn,
                tick=tick,
                actor_id="npc_mira",
                event_type="NPC_REQUESTED_RESOURCE",
                target_id="driftwood_1",
                location_id="workshop_yard",
                data={"resource_kind": "useful_wood"},
                summary="Mira requested useful wood for the workshop.",
            )

        return None

    def _advance_kaspar(
        self, conn: sqlite3.Connection, tick: int
    ) -> dict[str, object] | None:
        _, mira_state = self._load_runtime(conn, "npc_mira")
        if not bool(mira_state.get("requested_wood", False)):
            return None

        override_active, state = self._load_runtime(conn, "npc_kaspar")
        carrying_wood = self._state_int(state, "carrying_wood")
        if carrying_wood not in (0, 1):
            raise RuntimeError("npc_kaspar carrying_wood must be 0 or 1")

        goal = "deliver_wood" if carrying_wood else "collect_wood"
        state["carrying_wood"] = carrying_wood
        state["goal"] = goal
        location_id = self._actor_location(conn, "npc_kaspar")

        if carrying_wood == 0:
            if location_id != "river_edge":
                next_location = self._next_hop(conn, location_id, "river_edge")
                if next_location is None:
                    if override_active != 1 or state.get("goal") != goal:
                        self._save_runtime(
                            conn,
                            "npc_kaspar",
                            override_active=1,
                            state=state,
                            tick=tick,
                        )
                    return None
                conn.execute(
                    "UPDATE actors SET location_id = ? WHERE id = 'npc_kaspar'",
                    (next_location,),
                )
                self._save_runtime(
                    conn,
                    "npc_kaspar",
                    override_active=1,
                    state=state,
                    tick=tick,
                )
                return self._record_event(
                    conn,
                    tick=tick,
                    actor_id="npc_kaspar",
                    event_type="NPC_MOVED",
                    target_id="river_edge",
                    location_id=next_location,
                    data={
                        "from": location_id,
                        "to": next_location,
                        "goal": "collect_wood",
                    },
                    summary=f"Kaspar moved from {location_id} to {next_location} to collect wood.",
                )

            driftwood = conn.execute(
                "SELECT location_id, owner_actor_id FROM entities WHERE id = 'driftwood_1'"
            ).fetchone()
            if (
                driftwood is None
                or driftwood["location_id"] != "river_edge"
                or driftwood["owner_actor_id"] is not None
            ):
                if override_active != 1 or state.get("goal") != "collect_wood":
                    self._save_runtime(
                        conn,
                        "npc_kaspar",
                        override_active=1,
                        state=state,
                        tick=tick,
                    )
                elif override_active != 1:
                    self._save_runtime(
                        conn,
                        "npc_kaspar",
                        override_active=1,
                        state=state,
                        tick=tick,
                    )
                else:
                    self._save_runtime(
                        conn,
                        "npc_kaspar",
                        override_active=1,
                        state=state,
                        tick=tick,
                    )
                return None

            collected = conn.execute(
                "UPDATE entities SET location_id = NULL, owner_actor_id = NULL "
                "WHERE id = 'driftwood_1' AND location_id = 'river_edge' "
                "AND owner_actor_id IS NULL"
            )
            if collected.rowcount != 1:
                self._save_runtime(
                    conn,
                    "npc_kaspar",
                    override_active=1,
                    state=state,
                    tick=tick,
                )
                return None

            state["carrying_wood"] = 1
            state["goal"] = "deliver_wood"
            self._save_runtime(
                conn,
                "npc_kaspar",
                override_active=1,
                state=state,
                tick=tick,
            )
            return self._record_event(
                conn,
                tick=tick,
                actor_id="npc_kaspar",
                event_type="NPC_COLLECTED_RESOURCE",
                target_id="driftwood_1",
                location_id="river_edge",
                data={"resource_kind": "useful_wood", "amount": 1},
                summary="Kaspar collected the existing driftwood from the river edge.",
            )

        mira_location = self._actor_location(conn, "npc_mira")
        if location_id != mira_location:
            next_location = self._next_hop(conn, location_id, mira_location)
            if next_location is None:
                self._save_runtime(
                    conn,
                    "npc_kaspar",
                    override_active=1,
                    state=state,
                    tick=tick,
                )
                return None
            conn.execute(
                "UPDATE actors SET location_id = ? WHERE id = 'npc_kaspar'",
                (next_location,),
            )
            self._save_runtime(
                conn,
                "npc_kaspar",
                override_active=1,
                state=state,
                tick=tick,
            )
            return self._record_event(
                conn,
                tick=tick,
                actor_id="npc_kaspar",
                event_type="NPC_MOVED",
                target_id="npc_mira",
                location_id=next_location,
                data={
                    "from": location_id,
                    "to": next_location,
                    "goal": "deliver_wood",
                },
                summary=f"Kaspar moved from {location_id} to {next_location} to deliver wood.",
            )

        mira_override, mira_state = self._load_runtime(conn, "npc_mira")
        if not bool(mira_state.get("requested_wood", False)):
            return None
        mira_state["wood_stock"] = self._state_int(mira_state, "wood_stock") + 1
        mira_state["requested_wood"] = False
        self._save_runtime(
            conn,
            "npc_mira",
            override_active=0,
            state=mira_state,
            tick=tick,
        )
        state["carrying_wood"] = 0
        state["goal"] = None
        self._save_runtime(
            conn,
            "npc_kaspar",
            override_active=0,
            state=state,
            tick=tick,
        )
        return self._record_event(
            conn,
            tick=tick,
            actor_id="npc_kaspar",
            event_type="NPC_DELIVERED_RESOURCE",
            target_id="npc_mira",
            location_id=mira_location,
            data={"resource_kind": "useful_wood", "amount": 1},
            summary="Kaspar delivered one unit of useful wood to Mira.",
        )

    @staticmethod
    def _load_runtime(
        conn: sqlite3.Connection, npc_actor_id: str
    ) -> tuple[int, dict[str, object]]:
        row = conn.execute(
            "SELECT override_active, state_json FROM npc_runtime_state "
            "WHERE npc_actor_id = ?",
            (npc_actor_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"missing runtime state for {npc_actor_id}")
        state = json.loads(str(row["state_json"]))
        if not isinstance(state, dict):
            raise RuntimeError(f"invalid runtime state for {npc_actor_id}")
        return int(row["override_active"]), state

    @staticmethod
    def _save_runtime(
        conn: sqlite3.Connection,
        npc_actor_id: str,
        *,
        override_active: int,
        state: dict[str, object],
        tick: int,
    ) -> None:
        cursor = conn.execute(
            "UPDATE npc_runtime_state "
            "SET override_active = ?, state_json = ?, updated_tick = ? "
            "WHERE npc_actor_id = ?",
            (
                override_active,
                json.dumps(state, separators=(",", ":"), sort_keys=True),
                tick,
                npc_actor_id,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError(f"missing runtime state for {npc_actor_id}")

    @staticmethod
    def _actor_location(conn: sqlite3.Connection, actor_id: str) -> str:
        row = conn.execute(
            "SELECT location_id FROM actors WHERE id = ?", (actor_id,)
        ).fetchone()
        if row is None or row["location_id"] is None:
            raise RuntimeError(f"actor {actor_id} has no canonical location")
        return str(row["location_id"])

    @staticmethod
    def _state_int(state: dict[str, object], key: str) -> int:
        value = state.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise RuntimeError(f"runtime field {key} must be an integer")
        return value

    @staticmethod
    def _next_hop(
        conn: sqlite3.Connection, current_location: str, target_location: str
    ) -> str | None:
        if current_location == target_location:
            return None

        queue: deque[tuple[str, str | None]] = deque([(current_location, None)])
        visited = {current_location}
        while queue:
            location_id, first_hop = queue.popleft()
            neighbors = conn.execute(
                "SELECT to_location_id FROM location_edges "
                "WHERE from_location_id = ? ORDER BY to_location_id",
                (location_id,),
            ).fetchall()
            for row in neighbors:
                neighbor = str(row["to_location_id"])
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                candidate_first_hop = first_hop or neighbor
                if neighbor == target_location:
                    return candidate_first_hop
                queue.append((neighbor, candidate_first_hop))
        return None

    @staticmethod
    def _record_event(
        conn: sqlite3.Connection,
        *,
        tick: int,
        actor_id: str,
        event_type: str,
        target_id: str | None,
        location_id: str | None,
        data: dict[str, object],
        summary: str,
    ) -> dict[str, object]:
        if event_type not in _ALLOWED_EVENT_TYPES:
            raise ValueError(f"unsupported world event type: {event_type}")
        data_json = json.dumps(data, separators=(",", ":"), sort_keys=True)
        cursor = conn.execute(
            "INSERT INTO world_events "
            "(world_id, tick, actor_id, event_type, target_id, location_id, data_json, summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                DEFAULT_WORLD_ID,
                tick,
                actor_id,
                event_type,
                target_id,
                location_id,
                data_json,
                summary,
            ),
        )
        event_id = int(cursor.lastrowid)
        return {
            "id": event_id,
            "world_event_id": event_id,
            "world_id": DEFAULT_WORLD_ID,
            "tick": tick,
            "actor_id": actor_id,
            "event_type": event_type,
            "target_id": target_id,
            "location_id": location_id,
            "data": data,
            "summary": summary,
        }
