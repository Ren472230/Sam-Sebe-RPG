from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .day import DayService
from .db import GameDatabase


def build_playtest_report(
    db: GameDatabase, player_id: str = "player_1"
) -> dict[str, Any]:
    events = db.list_events(player_id)
    action_counts = Counter(event["action_type"] for event in events)
    locations = sorted(
        {
            event["location_id"]
            for event in events
            if event.get("location_id") is not None
        }
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
                """
                SELECT achievement_id
                FROM achievements
                WHERE player_id = ?
                ORDER BY achievement_id
                """,
                (player_id,),
            ).fetchall()
        ]
        abilities = [
            row["ability_id"]
            for row in conn.execute(
                """
                SELECT ability_id
                FROM abilities
                WHERE player_id = ?
                ORDER BY ability_id
                """,
                (player_id,),
            ).fetchall()
        ]
        npc_trust = {
            row["source_id"]: float(row["value"])
            for row in conn.execute(
                """
                SELECT source_id, value
                FROM relations
                WHERE target_id = ? AND relation_type = 'trust'
                ORDER BY source_id
                """,
                (player_id,),
            ).fetchall()
            if row["source_id"]
            in {"mira_craftswoman", "oren_innkeeper", "kaspar_forager"}
        }
        animal_trust: dict[str, int] = {}
        for row in conn.execute(
            """
            SELECT entity_id, state_json
            FROM entities
            WHERE entity_type = 'animal'
            ORDER BY entity_id
            """
        ).fetchall():
            state = json.loads(row["state_json"])
            animal_trust[row["entity_id"]] = int(state.get("trust", 0))

    resources = db.fetch_player_resources(player_id) or {
        "coins": 0,
        "lodging_secured": False,
    }
    world_time = db.get_world_time()
    return {
        "player_id": player_id,
        "world_time": world_time,
        "total_events": len(events),
        "failed_events": sum(not event["success"] for event in events),
        "action_counts": dict(sorted(action_counts.items())),
        "unique_action_types": len(action_counts),
        "locations_touched": locations,
        "throwing": throwing,
        "achievements": achievements,
        "abilities": abilities,
        "first_day": {
            "coins": resources["coins"],
            "lodging_secured": resources["lodging_secured"],
            "phase": DayService().phase(world_time),
            "npc_trust": npc_trust,
            "animal_trust": animal_trust,
        },
    }
