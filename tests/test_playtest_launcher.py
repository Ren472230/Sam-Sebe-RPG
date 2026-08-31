from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "playtest.py"


def _load_launcher():
    assert SCRIPT.exists(), "scripts/playtest.py must provide the single playtest entry point"
    spec = importlib.util.spec_from_file_location("sam_sebe_playtest_launcher", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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


@pytest.mark.skipif(os.name == "nt", reason="POSIX process-group regression proof")
def test_managed_process_stop_terminates_child_process_tree(tmp_path: Path) -> None:
    launcher = _load_launcher()
    child_pid_file = tmp_path / "child.pid"
    parent_code = (
        "from pathlib import Path; import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8'); "
        "time.sleep(60)"
    )

    parent = launcher._start_process(
        [sys.executable, "-c", parent_code, str(child_pid_file)],
        cwd=ROOT,
        env=os.environ.copy(),
    )
    child_pid: int | None = None
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not child_pid_file.exists():
            time.sleep(0.05)
        assert child_pid_file.exists(), "parent process did not publish its child PID"
        child_pid = int(child_pid_file.read_text(encoding="utf-8"))
        assert _pid_exists(child_pid)

        launcher._stop(parent)

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and _pid_exists(child_pid):
            time.sleep(0.05)
        assert not _pid_exists(child_pid), "managed stop left a child process running"
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        if child_pid is not None and _pid_exists(child_pid):
            os.kill(child_pid, signal.SIGKILL)
