from pathlib import Path

from samseberpg.cli import HELP, _print_state
from samseberpg.db import GameDatabase


def make_db(tmp_path: Path) -> GameDatabase:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize(); db.bootstrap_if_empty()
    return db


def test_state_shows_day_money_and_lodging_without_quest_log(tmp_path: Path, capsys) -> None:
    db = make_db(tmp_path)
    _print_state(db)
    out = capsys.readouterr().out.lower()
    assert "утро" in out
    assert "монеты: 0" in out
    assert "ночлег: нет" in out
    assert "квест" not in out


def test_help_exposes_social_verbs_but_not_a_solution_checklist() -> None:
    low = HELP.lower()
    assert "поговорить" in low
    assert "дать" in low
    assert "покормить" in low
    assert "спросить" in low and "ночлег" in low
    assert "получи 3" not in low


def test_intro_frames_a_soft_life_problem_without_assigning_a_class() -> None:
    import samseberpg.cli as cli
    assert hasattr(cli, "INTRO")
    low = cli.INTRO.lower()
    assert "нов" in low
    assert "ноч" in low
    assert "класс" not in low
    assert "квест" not in low
