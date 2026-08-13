from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.reporting import build_playtest_report


def test_report_includes_first_day_state_and_relationships(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    with db.connect() as conn:
        conn.execute("UPDATE player_resources SET coins=2, lodging_secured=1 WHERE player_id='player_1'")
        conn.execute("INSERT INTO relations(source_id,target_id,relation_type,value) VALUES ('mira_craftswoman','player_1','trust',2)")
        conn.execute("UPDATE entities SET state_json='{\"trust\":3,\"fear\":0}' WHERE entity_id='raven_1'")
        conn.execute("UPDATE world_meta SET value='12' WHERE key='world_time'")
    report = build_playtest_report(db)
    assert report["first_day"]["coins"] == 2
    assert report["first_day"]["lodging_secured"] is True
    assert report["first_day"]["npc_trust"]["mira_craftswoman"] == 2
    assert report["first_day"]["animal_trust"]["raven_1"] == 3
    assert report["first_day"]["phase"] == "вечер"
