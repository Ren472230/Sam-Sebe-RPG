from __future__ import annotations

from collections import Counter
from typing import Any

from .db import GameDatabase


def build_playtest_report(
    db: GameDatabase, player_id: str = "player_1"
) -> dict[str, Any]:
    events = db.list_events(player_id)
    action_counts = Counter(event["action_type"] for event in events)
    locations = sorted(
        {event["location_id"] for event in events if event.get("location_id") is not None}
    )
    throwing = db.fetch_behavior_profile(player_id, "throwing") or {
        "attempts": 0,
        "hits": 0,
        "targets": [],
        "projectile_types": [],
        "locations": [],
    }

    with db.connect() as conn:
        achievements = [
            row["achievement_id"]
            for row in conn.execute(
                "SELECT achievement_id FROM achievements WHERE player_id = ? ORDER BY achievement_id",
                (player_id,),
            ).fetchall()
        ]
        abilities = [
            row["ability_id"]
            for row in conn.execute(
                "SELECT ability_id FROM abilities WHERE player_id = ? ORDER BY ability_id",
                (player_id,),
            ).fetchall()
        ]

    return {
        "player_id": player_id,
        "world_time": db.get_world_time(),
        "total_events": len(events),
        "failed_events": sum(not event["success"] for event in events),
        "action_counts": dict(sorted(action_counts.items())),
        "unique_action_types": len(action_counts),
        "locations_touched": locations,
        "throwing": throwing,
        "achievements": achievements,
        "abilities": abilities,
    }
