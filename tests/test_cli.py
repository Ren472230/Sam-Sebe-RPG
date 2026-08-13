from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_cli_one_shot_look_bootstraps_and_renders_location(tmp_path: Path, capsys) -> None:
    try:
        from samseberpg.cli import main
    except ImportError as exc:
        pytest.fail(f"CLI is not implemented yet: {exc}")

    exit_code = main(["--db", str(tmp_path / "game.db"), "--command", "осмотреться"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Двор мастерской" in output
    assert "Мира" in output
    assert "Старая бочка" in output
