import subprocess
import sys
from pathlib import Path


def test_first_day_demo_reaches_lodging_and_optional_animal_interaction(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "first_day.db"
    proc = subprocess.run(
        [sys.executable, str(repo / "scripts" / "demo_first_day.py"), "--db", str(db_path)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "FIRST DAY DEMO PASS" in proc.stdout
    assert "lodging_secured=True" in proc.stdout
    assert "raven_trust=1" in proc.stdout
