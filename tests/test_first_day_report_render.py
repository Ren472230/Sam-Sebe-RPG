from scripts.playtest_report import render_human


def test_human_report_renders_first_day_signals() -> None:
    report = {
        "player_id": "player_1",
        "world_time": 12,
        "total_events": 3,
        "failed_events": 0,
        "unique_action_types": 2,
        "action_counts": {"TALK": 1, "GIVE": 2},
        "throwing": {"attempts": 0, "hits": 0, "targets": [], "projectile_types": [], "locations": []},
        "achievements": [],
        "abilities": [],
        "first_day": {
            "coins": 1,
            "lodging_secured": True,
            "phase": "вечер",
            "npc_trust": {"mira_craftswoman": 2},
            "animal_trust": {"raven_1": 1},
        },
    }
    text = render_human(report)
    assert "Монеты: 1" in text
    assert "Ночлег: есть" in text
    assert "Фаза дня: вечер" in text
    assert "mira_craftswoman: 2" in text
    assert "raven_1: 1" in text


def test_human_report_renders_autonomous_world_events_separately() -> None:
    report = {
        "player_id": "player_1",
        "world_time": 9,
        "total_events": 1,
        "failed_events": 0,
        "unique_action_types": 1,
        "action_counts": {"WAIT": 1},
        "throwing": {"attempts": 0, "hits": 0, "targets": [], "projectile_types": [], "locations": []},
        "achievements": [],
        "abilities": [],
        "world_events_total": 7,
        "world_event_counts": {
            "NPC_WORKED": 2,
            "NPC_REQUESTED_RESOURCE": 1,
            "NPC_COLLECTED_RESOURCE": 1,
            "NPC_MOVED": 2,
            "NPC_DELIVERED_RESOURCE": 1,
        },
        "latest_world_events": [
            {
                "world_time": 8,
                "actor_id": "kaspar_forager",
                "event_type": "NPC_DELIVERED_RESOURCE",
                "summary": "Каспар приносит Мире найденную древесину.",
            }
        ],
        "first_day": {
            "coins": 0,
            "lodging_secured": False,
            "phase": "под вечер",
            "npc_trust": {},
            "animal_trust": {},
        },
    }

    text = render_human(report)
    assert "Автономные события мира: 7" in text
    assert "NPC_DELIVERED_RESOURCE: 1" in text
    assert "t=8 kaspar_forager" in text
    assert "WAIT: 1" in text
