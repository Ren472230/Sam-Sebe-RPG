from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_demo_script_proves_complete_vertical_loop() -> None:
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    completed = subprocess.run(
        [sys.executable, str(project_root / "scripts" / "demo_pilot.py")],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "aimed_throw: unlocked" in completed.stdout
    assert "aimed_accuracy: 55%" in completed.stdout
    assert "DEMO PASS" in completed.stdout
