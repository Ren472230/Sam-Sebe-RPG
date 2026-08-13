from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PS1 = ROOT / "scripts" / "windows" / "setup_and_run.ps1"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_root_launchers_exist_and_delegate_to_one_script():
    launchers = {
        "Играть.bat": "PlayFounder",
        "Играть_системный_режим.bat": "PlaySystems",
        "Сбросить_мир.bat": "ResetSave",
    }
    for filename, action in launchers.items():
        text = read(ROOT / filename)
        assert "setup_and_run.ps1" in text
        assert f"-Action {action}" in text
        assert "%~dp0" in text


def test_launcher_declares_exact_actions_and_python_floor():
    text = read(PS1)
    assert "PlayFounder" in text
    assert "PlaySystems" in text
    assert "ResetSave" in text
    assert "3.12" in text
    assert "Find-CompatiblePython" in text


def test_runtime_install_is_local_and_excludes_dev_dependencies():
    text = read(PS1)
    assert ".venv" in text
    assert "pip" in text
    assert "install" in text
    assert "-e" in text
    assert "[dev]" not in text


def test_save_paths_are_distinct_and_scoped_to_playtests():
    text = read(PS1).replace("\\", "/")
    assert 'Join-Path $PlaytestsDir "founder-free.db"' in text
    assert 'Join-Path $PlaytestsDir "founder-systems.db"' in text
    assert '$PlaytestsDir = Join-Path $RepoRoot "playtests"' in text


def test_launcher_never_auto_installs_external_tools_or_models():
    text = read(PS1).lower()
    forbidden = [
        "winget install",
        "choco install",
        "scoop install",
        "ollama pull",
        "set-executionpolicy",
        "reg add",
    ]
    for command in forbidden:
        assert command not in text


def test_reset_is_confirmation_gated_and_limited_to_known_saves():
    text = read(PS1)
    assert "Reset-PlaytestSave" in text
    assert "founder-free.db" in text
    assert "founder-systems.db" in text
    assert "Read-Host" in text
    assert "Remove-Item" in text
    assert 'if ($confirmation -ne "DELETE")' in text


def test_founder_model_resolution_never_requires_download():
    text = read(PS1)
    assert "Get-OllamaModels" in text
    assert "Resolve-FounderModel" in text
    assert "SAM_SEBE_OLLAMA_MODEL" in text
    assert "ollama" in text.lower()
    assert " list" in text.lower()


def test_batch_wrappers_pause_only_on_failure():
    for filename in (
        "Играть.bat",
        "Играть_системный_режим.bat",
        "Сбросить_мир.bat",
    ):
        text = read(ROOT / filename)
        assert "if not \"%EXIT_CODE%\"==\"0\"" in text
        assert "pause" in text.lower()


def test_launcher_uses_version_stamp_in_repository_venv():
    text = read(PS1)
    assert '$VenvDir = Join-Path $RepoRoot ".venv"' in text
    assert '$StampPath = Join-Path $VenvDir ".sam-sebe-launcher-version"' in text
    assert '$LauncherContractVersion = "1"' in text


def test_windows_powershell_script_has_utf8_bom():
    assert PS1.read_bytes().startswith(b"\xef\xbb\xbf")
