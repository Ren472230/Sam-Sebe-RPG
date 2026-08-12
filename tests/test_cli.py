from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_cli_boots_persistent_world_and_quits_cleanly(tmp_path: Path) -> None:
    db_path = tmp_path / "cli.db"
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    completed = subprocess.run(
        [sys.executable, "-m", "samseberpg.cli", "--db", str(db_path)],
        input="quit\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    assert "Sam-Sebe-RPG Pilot v0.1" in completed.stdout
    assert "workshop_yard" in completed.stdout
    assert db_path.exists()
