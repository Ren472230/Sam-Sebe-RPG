from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.reporting import build_playtest_report


def test_playtest_report_summarizes_event_evidence(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=1)

    game.execute(CanonicalAction("player_1", ActionType.LOOK))
    game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="pinecone_1"))
    game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1"))
    game.execute(
        CanonicalAction(
            "player_1",
            ActionType.THROW,
            item_id="stone_flat_1",
            target_id="target_barrel",
        )
    )

    report = build_playtest_report(db)

    assert report["total_events"] == 4
    assert report["failed_events"] == 1
    assert report["action_counts"] == {"LOOK": 1, "TAKE": 2, "THROW": 1}
    assert report["unique_action_types"] == 3
    assert report["locations_touched"] == ["workshop_yard"]
    assert report["throwing"]["attempts"] == 1
    assert report["throwing"]["targets"] == ["target_barrel"]
    assert report["achievements"] == []
    assert report["abilities"] == []


def test_playtest_report_script_reads_existing_database(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    db = GameDatabase(tmp_path / "session.db")
    db.initialize()
    db.bootstrap_if_empty()
    game = GameService(db, seed=1)
    game.execute(CanonicalAction("player_1", ActionType.LOOK))

    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")
    completed = subprocess.run(
        [
            sys.executable,
            str(project_root / "scripts" / "playtest_report.py"),
            str(db.path),
        ],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "Всего событий: 1" in completed.stdout
    assert "LOOK: 1" in completed.stdout
