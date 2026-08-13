from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_demo_script_proves_complete_progression_loop(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo_root / "src")
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "demo_pilot.py"),
            "--db",
            str(tmp_path / "demo.db"),
        ],
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "hand_remembers_arc" in completed.stdout
    assert "aimed_throw" in completed.stdout
    assert "AIMED THROW" in completed.stdout
    assert "DEMO PASS" in completed.stdout
