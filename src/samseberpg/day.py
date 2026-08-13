from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any


TickCallback = Callable[[sqlite3.Connection, int], Any]


class DayService:
    def advance(
        self,
        conn: sqlite3.Connection,
        ticks: int,
        *,
        on_tick: TickCallback | None = None,
    ) -> int:
        row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        current = int(row["value"]) if row else 0

        for world_time in range(current + 1, current + ticks + 1):
            conn.execute(
                "UPDATE world_meta SET value = ? WHERE key = 'world_time'",
                (str(world_time),),
            )
            self.apply_schedules(conn, world_time)
            if on_tick is not None:
                on_tick(conn, world_time)

        return current + ticks

    def phase(self, world_time: int) -> str:
        if world_time < 4:
            return "утро"
        if world_time < 8:
            return "день"
        if world_time < 12:
            return "под вечер"
        return "вечер"

    def apply_schedules(self, conn: sqlite3.Connection, world_time: int) -> None:
        # Living World v0 owns Mira/Kaspar movement. Oren remains at the square.
        _ = (conn, world_time)
