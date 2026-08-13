from pathlib import Path

from samseberpg.db import GameDatabase
from samseberpg.reporting import build_playtest_report
from scripts.playtest_report import render_human


def make_db(tmp_path: Path) -> GameDatabase:
    db = GameDatabase(tmp_path / "report.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db


def test_report_aggregates_input_attempts_without_requiring_raw_text(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    first = db.record_input_attempt(
        world_time=0,
        raw_text="осмотреться",
        parser_mode="deterministic",
        parser_model=None,
        recognized=True,
        canonical_action={"action_type": "LOOK"},
        parser_error=None,
        latency_ms=0.2,
    )
    db.complete_input_attempt(first, "OK")
    db.record_input_attempt(
        world_time=0,
        raw_text="насвистываю мелодию",
        parser_mode="none",
        parser_model=None,
        recognized=False,
        canonical_action=None,
        parser_error=None,
        latency_ms=0.1,
    )
    db.record_input_attempt(
        world_time=0,
        raw_text="осмотрю крышу внимательнее",
        parser_mode="ollama",
        parser_model="local-test",
        recognized=False,
        canonical_action=None,
        parser_error="Ollama request failed",
        latency_ms=12.0,
    )

    report = build_playtest_report(db)

    assert report["input_attempts_total"] == 3
    assert report["recognized_inputs"] == 1
    assert report["unrecognized_inputs"] == 2
    assert report["parser_mode_counts"] == {
        "deterministic": 1,
        "none": 1,
        "ollama": 1,
    }
    assert report["parser_error_counts"] == {"ollama": 1}
    assert "raw_inputs" not in report


def test_human_report_shows_input_aggregates_but_not_raw_player_text(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    secret_text = "мой уникальный секретный ввод"
    db.record_input_attempt(
        world_time=0,
        raw_text=secret_text,
        parser_mode="none",
        parser_model=None,
        recognized=False,
        canonical_action=None,
        parser_error=None,
        latency_ms=0.1,
    )

    text = render_human(build_playtest_report(db))

    assert "Попыток ввода: 1" in text
    assert "Распознано: 0" in text
    assert "Не распознано: 1" in text
    assert secret_text not in text
