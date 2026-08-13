from __future__ import annotations

import sqlite3


class DayService:
    def advance(self, conn: sqlite3.Connection, ticks: int) -> int:
        row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        current = int(row["value"]) if row else 0
        new_time = current + ticks
        conn.execute(
            "UPDATE world_meta SET value = ? WHERE key = 'world_time'",
            (str(new_time),),
        )
        self.apply_schedules(conn, new_time)
        return new_time

    def phase(self, world_time: int) -> str:
        if world_time < 4:
            return "утро"
        if world_time < 8:
            return "день"
        if world_time < 12:
            return "под вечер"
        return "вечер"

    def apply_schedules(self, conn: sqlite3.Connection, world_time: int) -> None:
        if world_time >= 8:
            conn.execute(
                "UPDATE entities SET location_id = 'village_square' WHERE entity_id IN ('mira_craftswoman', 'kaspar_forager')"
            )
