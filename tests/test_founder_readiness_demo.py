import subprocess
import sys
from pathlib import Path


def test_founder_readiness_demo_proves_audit_fix_pack(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "founder-ready.db"
    proc = subprocess.run(
        [
            sys.executable,
            str(repo / "scripts" / "demo_founder_readiness.py"),
            "--db",
            str(db_path),
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "schema_version=2" in proc.stdout
    assert "input_telemetry=PASS" in proc.stdout
    assert "observable_world=PASS" in proc.stdout
    assert "social_route=PASS" in proc.stdout
    assert "hostile_consequence=PASS" in proc.stdout
    assert "precision_utility=PASS" in proc.stdout
    assert "FOUNDER READINESS DEMO PASS" in proc.stdout
