from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .db import to_utc_text


class WorldSynchronizer:
    def catch_up(self, conn, world_id: str, now: datetime) -> list[str]:
        world = conn.execute(
            "SELECT timezone, last_simulated_at FROM worlds WHERE id = ?",
            (world_id,),
        ).fetchone()
        if world is None:
            raise KeyError(f"unknown world: {world_id}")

        last = datetime.fromisoformat(world["last_simulated_at"])
        if now < last:
            return []

        local_now = now.astimezone(ZoneInfo(world["timezone"]))
        minute = local_now.hour * 60 + local_now.minute
        changed: list[str] = []
        npc_rows = conn.execute("SELECT actor_id FROM npcs ORDER BY actor_id").fetchall()

        for npc_row in npc_rows:
            schedule_rows = conn.execute(
                """
                SELECT start_minute_local, end_minute_local, location_id, activity
                FROM npc_schedule
                WHERE npc_actor_id = ?
                ORDER BY priority DESC, id ASC
                """,
                (npc_row["actor_id"],),
            ).fetchall()
            applicable = next(
                (
                    row
                    for row in schedule_rows
                    if self._matches(
                        row["start_minute_local"], row["end_minute_local"], minute
                    )
                ),
                None,
            )
            if applicable is None:
                continue

            current = conn.execute(
                """
                SELECT a.location_id, n.current_activity
                FROM actors a JOIN npcs n ON n.actor_id = a.id
                WHERE a.id = ?
                """,
                (npc_row["actor_id"],),
            ).fetchone()
            if (
                current["location_id"] != applicable["location_id"]
                or current["current_activity"] != applicable["activity"]
            ):
                conn.execute(
                    "UPDATE actors SET location_id = ? WHERE id = ?",
                    (applicable["location_id"], npc_row["actor_id"]),
                )
                conn.execute(
                    "UPDATE npcs SET current_activity = ? WHERE actor_id = ?",
                    (applicable["activity"], npc_row["actor_id"]),
                )
                changed.append(npc_row["actor_id"])

        conn.execute(
            "UPDATE worlds SET last_simulated_at = ? WHERE id = ?",
            (to_utc_text(now), world_id),
        )
        return changed

    @staticmethod
    def _matches(start: int, end: int, minute: int) -> bool:
        if start == end:
            return True
        if start < end:
            return start <= minute < end
        return minute >= start or minute < end
