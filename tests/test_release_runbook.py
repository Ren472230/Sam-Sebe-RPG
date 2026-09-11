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


def test_human_playtest_securely_prompts_for_openai_key_when_missing() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "PLAY_SAM_SEBE_RPG.bat").read_text(encoding="utf-8")
    runner = (root / "RUN_STREAM_SLICE.ps1").read_text(encoding="utf-8")

    assert "-PromptForOpenAIKey" in launcher
    assert "[switch]$PromptForOpenAIKey" in runner
    assert "Read-Host" in runner
    assert "-AsSecureString" in runner
    assert "SecureStringToBSTR" in runner
    assert "$env:OPENAI_API_KEY" in runner


def test_fresh_zip_launcher_bootstraps_reproducible_dependencies_and_keeps_errors_visible() -> None:
    root = Path(__file__).resolve().parents[1]
    launcher = (root / "PLAY_SAM_SEBE_RPG.bat").read_text(encoding="utf-8")
    runner = (root / "RUN_STREAM_SLICE.ps1").read_text(encoding="utf-8")

    assert "powershell.exe -NoExit" in launcher
    assert 'Get-Command python' in runner
    assert 'python -c "import samseberpg"' in runner
    assert 'constraints/python-3.12.txt' in runner.replace("\\", "/")
    assert 'python -m pip install -c $PythonConstraints -e ".[dev]"' in runner
    assert 'Get-Command npm' in runner
    assert '$WebNodeModules = Join-Path $Root "web/node_modules"' in runner
    assert '$WebLockfile = Join-Path $Root "web/package-lock.json"' in runner
    assert 'if (Test-Path $WebLockfile)' in runner
    assert 'npm ci --no-audit --no-fund' in runner
    assert 'npm install --no-audit --no-fund' in runner
    assert "Installing local Python package and constrained test/runtime dependencies" in runner
    assert "Installing web dependencies" in runner
