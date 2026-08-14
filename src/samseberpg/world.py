from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class WorldSynchronizer:
    def catch_up(self, conn, world_id: str, now: datetime) -> None:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("world clock datetime must be timezone-aware")
        now_utc = now.astimezone(timezone.utc)
        world = conn.execute(
            "SELECT timezone, last_simulated_at FROM worlds WHERE id = ?",
            (world_id,),
        ).fetchone()
        if world is None:
            raise LookupError(f"world not found: {world_id}")

        last_simulated_at = world[1]
        if last_simulated_at is not None:
            last = datetime.fromisoformat(str(last_simulated_at).replace("Z", "+00:00"))
            if last >= now_utc:
                return

        local_now = now_utc.astimezone(ZoneInfo(str(world[0])))
        minute = local_now.hour * 60 + local_now.minute

        npc_ids = [
            str(row[0])
            for row in conn.execute(
                "SELECT npcs.actor_id FROM npcs "
                "JOIN actors ON actors.id = npcs.actor_id "
                "WHERE actors.world_id = ? ORDER BY npcs.actor_id",
                (world_id,),
            ).fetchall()
        ]
        for npc_id in npc_ids:
            rows = conn.execute(
                "SELECT start_minute_local, end_minute_local, location_id, activity "
                "FROM npc_schedule WHERE npc_actor_id = ? "
                "ORDER BY priority DESC, id ASC",
                (npc_id,),
            ).fetchall()
            chosen = next((row for row in rows if _window_contains(row[0], row[1], minute)), None)
            if chosen is None:
                continue
            conn.execute(
                "UPDATE actors SET location_id = ? WHERE id = ? AND location_id IS NOT ?",
                (chosen[2], npc_id, chosen[2]),
            )
            conn.execute(
                "UPDATE npcs SET current_activity = ? WHERE actor_id = ? AND current_activity <> ?",
                (chosen[3], npc_id, chosen[3]),
            )

        conn.execute(
            "UPDATE worlds SET last_simulated_at = ? WHERE id = ?",
            (_timestamp(now_utc), world_id),
        )


def _window_contains(start: int, end: int, minute: int) -> bool:
    if start == end:
        return True
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
