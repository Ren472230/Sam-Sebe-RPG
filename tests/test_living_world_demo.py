import subprocess
import sys
from pathlib import Path


def test_living_world_demo_proves_autonomous_chain_and_persistence(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "living_world.db"
    proc = subprocess.run(
        [sys.executable, str(repo / "scripts" / "demo_living_world.py"), "--db", str(db_path)],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "NPC_REQUESTED_RESOURCE" in proc.stdout
    assert "NPC_COLLECTED_RESOURCE" in proc.stdout
    assert "NPC_DELIVERED_RESOURCE" in proc.stdout
    assert "persistence: PASS" in proc.stdout
    assert "LIVING WORLD DEMO PASS" in proc.stdout
