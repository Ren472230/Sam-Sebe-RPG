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
