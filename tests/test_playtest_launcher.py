from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "playtest.py"


def _load_launcher():
    assert SCRIPT.exists(), "scripts/playtest.py must provide the single playtest entry point"
    spec = importlib.util.spec_from_file_location("sam_sebe_playtest_launcher", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_launcher_has_non_destructive_preflight_mode() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PLAYTEST PREFLIGHT: PASS" in completed.stdout


def test_reset_save_removes_sqlite_sidecars_only_for_requested_path(tmp_path: Path) -> None:
    launcher = _load_launcher()
    database = tmp_path / "world.sqlite3"
    unrelated = tmp_path / "keep.txt"
    for path in (database, Path(f"{database}-wal"), Path(f"{database}-shm"), unrelated):
        path.write_text("x", encoding="utf-8")

    launcher.reset_save(database)

    assert not database.exists()
    assert not Path(f"{database}-wal").exists()
    assert not Path(f"{database}-shm").exists()
    assert unrelated.read_text(encoding="utf-8") == "x"
