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


def test_cli_look_renders_entities_and_exits(tmp_path: Path) -> None:
    db_path = tmp_path / "look.db"
    project_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root / "src")

    completed = subprocess.run(
        [sys.executable, "-m", "samseberpg.cli", "--db", str(db_path)],
        input="осмотреться\nquit\n",
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )

    assert completed.returncode == 0
    assert "Выходы: village_square" in completed.stdout
    assert "target_barrel" in completed.stdout
    assert "stone_flat_1" in completed.stdout


def test_resolve_player_input_uses_ollama_only_after_deterministic_parser(tmp_path: Path) -> None:
    from samseberpg.cli import resolve_player_input
    from samseberpg.db import GameDatabase
    from samseberpg.domain import ActionType, CanonicalAction

    db = GameDatabase(tmp_path / "resolve.db")
    db.initialize()
    db.bootstrap_if_empty()

    class FakeOllama:
        def __init__(self) -> None:
            self.calls = 0
            self.context = None

        def parse(self, text: str, context: dict[str, object], player_id: str = "player_1"):
            self.calls += 1
            self.context = context
            return CanonicalAction(player_id, ActionType.LOOK, source_text=text)

    fake = FakeOllama()
    deterministic = resolve_player_input("осмотреться", db, fake)
    natural = resolve_player_input("Огляжусь вокруг повнимательнее", db, fake)

    assert deterministic is not None
    assert deterministic.action_type == ActionType.LOOK
    assert fake.calls == 1
    assert natural is not None
    assert natural.action_type == ActionType.LOOK
    assert fake.context["location_id"] == "workshop_yard"
