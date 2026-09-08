from pathlib import Path


CURRENT_WORLD_READY_CHAMPION = "4b5d0e69c7542d315b277a18a102f8ee7b88bd96"
OBSOLETE_STREAM_SLICE_SHA = "e07472d3e7e3182363ec93518b0707e7fc35d2c1"


def test_stream_slice_runbook_records_current_world_ready_release_evidence() -> None:
    root = Path(__file__).resolve().parents[1]
    runbook = (root / "docs" / "release" / "STREAM_SLICE_V1.md").read_text(encoding="utf-8")

    assert CURRENT_WORLD_READY_CHAMPION in runbook
    assert OBSOLETE_STREAM_SLICE_SHA not in runbook
    assert "#47" in runbook
    assert "Living Conversation" in runbook
    assert "199 passed" in runbook
    assert "34170647631" in runbook
    assert "34170647639" in runbook
    assert "34170647629" in runbook
    assert "34170647627" in runbook
    assert "34170647628" in runbook


def test_human_playtest_has_one_click_normal_mode_launcher() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher_path = root / "PLAY_SAM_SEBE_RPG.bat"

    assert launcher_path.exists()
    launcher = launcher_path.read_text(encoding="utf-8")
    assert "RUN_STREAM_SLICE.ps1" in launcher
    assert "-Reset" in launcher
    assert "http://127.0.0.1:5173/" in launcher
    assert "?stream=1" not in launcher
    assert "Invoke-WebRequest" in launcher

    readme = (root / "README.md").read_text(encoding="utf-8")
    assert "PLAY_SAM_SEBE_RPG.bat" in readme
