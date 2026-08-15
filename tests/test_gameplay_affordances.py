from __future__ import annotations

import json
from pathlib import Path

from samseberpg.db import GameDatabase


def test_fresh_world_contains_minimal_throw_buy_use_affordances(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        rows = {
            row["id"]: row
            for row in conn.execute(
                "SELECT id, location_id, portable, state_json FROM entities "
                "WHERE id IN ('stone_flat_1', 'smooth_pebble_1', 'bottle_1', 'village_well', 'tavern_sign')"
            )
        }

    assert set(rows) == {
        "stone_flat_1",
        "smooth_pebble_1",
        "bottle_1",
        "village_well",
        "tavern_sign",
    }
    assert json.loads(rows["stone_flat_1"]["state_json"])["throwable"] is True
    assert json.loads(rows["stone_flat_1"]["state_json"])["impact_damage"] == 20
    assert json.loads(rows["smooth_pebble_1"]["state_json"])["throwable"] is True
    assert json.loads(rows["bottle_1"]["state_json"]) == {
        "fillable": True,
        "filled_with": None,
        "for_sale_by": "npc_oren",
        "price": 3,
    }
    assert rows["bottle_1"]["location_id"] == "village_square"
    assert bool(rows["bottle_1"]["portable"]) is True
    assert json.loads(rows["village_well"]["state_json"])["water_source"] is True
    assert bool(rows["village_well"]["portable"]) is False
    assert json.loads(rows["tavern_sign"]["state_json"])["condition"] == 100


def test_reinitialize_merges_missing_defaults_without_resetting_existing_state(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE id = 'stone_flat_1'",
            (json.dumps({"custom_player_mark": "keep-me"}),),
        )
        conn.execute("DELETE FROM entities WHERE id IN ('bottle_1', 'village_well', 'tavern_sign')")

    db.initialize()

    with db.connect() as conn:
        stone_state = json.loads(
            conn.execute("SELECT state_json FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
        )
        restored = {
            row[0]
            for row in conn.execute(
                "SELECT id FROM entities WHERE id IN ('bottle_1', 'village_well', 'tavern_sign')"
            )
        }

    assert stone_state == {
        "custom_player_mark": "keep-me",
        "impact_damage": 20,
        "throwable": True,
    }
    assert restored == {"bottle_1", "village_well", "tavern_sign"}


def test_reinitialize_does_not_overwrite_an_existing_affordance_value(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()

    with db.connect() as conn:
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE id = 'stone_flat_1'",
            (json.dumps({"throwable": False, "impact_damage": 7}),),
        )

    db.initialize()

    with db.connect() as conn:
        state = json.loads(
            conn.execute("SELECT state_json FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
        )

    assert state["throwable"] is False
    assert state["impact_damage"] == 7
