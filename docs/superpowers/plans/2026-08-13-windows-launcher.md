# Windows Double-Click Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Pilot playable on Ren's Windows PC by double-clicking root launcher files that bootstrap a repository-local Python environment, preserve saves, and optionally use an already-installed Ollama model without installing external software.

**Architecture:** Three thin root `.bat` entrypoints delegate all orchestration to one `scripts/windows/setup_and_run.ps1`. The PowerShell script owns Python discovery, `.venv` bootstrap, editable install, Ollama/model discovery, safe save reset, and final CLI invocation; gameplay remains entirely inside the existing `sam-sebe-rpg` CLI.

**Tech Stack:** Windows batch, Windows PowerShell 5.1-compatible syntax, Python 3.12+, pytest static contract tests, existing setuptools console entrypoint.

## Global Constraints

- Target only a Windows repository checkout for this MVP; no portable ZIP, MSI, `.exe`, Discord server, or web deployment.
- Never automatically install Python, Ollama, or Ollama models.
- Never execute `winget install`, `choco install`, `scoop install`, `ollama pull`, registry edits, PATH edits, firewall changes, or PowerShell execution-policy changes outside the launched process.
- Python must be version 3.12 or newer.
- Runtime environment must live at `.venv/` inside the repository.
- Runtime install command is `.venv\Scripts\python.exe -m pip install -e .`; playing must not install `.[dev]`.
- Founder save is `playtests/founder-free.db`; systems save is `playtests/founder-systems.db`.
- Reset may delete only those two known save files and must require explicit confirmation.
- Missing Ollama or a usable local model must leave systems mode available.
- Do not modify gameplay rules or parser semantics.

---

## File Structure

- Create `Играть.bat` — founder-oriented double-click entrypoint; delegates to PowerShell with `-Action PlayFounder`.
- Create `Играть_системный_режим.bat` — deterministic diagnostic entrypoint; delegates with `-Action PlaySystems`.
- Create `Сбросить_мир.bat` — safe reset entrypoint; delegates with `-Action ResetSave`.
- Create `scripts/windows/setup_and_run.ps1` — all Windows setup/launch orchestration.
- Create `tests/test_windows_launcher.py` — platform-independent contract tests for launcher safety and wiring.
- Modify `README.md` — make Windows double-click launch the primary personal-playtest path while retaining manual CLI documentation.

---

### Task 1: Lock the launcher safety contract with failing tests

**Files:**
- Create: `tests/test_windows_launcher.py`

**Interfaces:**
- Consumes: repository files as UTF-8 text through `pathlib.Path`.
- Produces: pytest contract tests that later launcher files must satisfy.

- [ ] **Step 1: Write the failing tests**

Create tests that assert:

```python
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
    assert '.venv' in text
    assert 'pip' in text
    assert 'install' in text
    assert '-e' in text
    assert '[dev]' not in text


def test_save_paths_are_distinct_and_scoped_to_playtests():
    text = read(PS1)
    assert "playtests/founder-free.db" in text.replace("\\", "/")
    assert "playtests/founder-systems.db" in text.replace("\\", "/")


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


def test_founder_model_resolution_never_requires_download():
    text = read(PS1)
    assert "Get-OllamaModels" in text
    assert "Resolve-FounderModel" in text
    assert "SAM_SEBE_OLLAMA_MODEL" in text
    assert "ollama list" in text.lower() or "& $OllamaCommand list" in text
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
python -m pytest -q tests/test_windows_launcher.py
```

Expected: FAIL because the launcher files do not exist yet.

- [ ] **Step 3: Commit only the RED contract**

```bash
git add tests/test_windows_launcher.py
git commit -m "test: define Windows launcher contract"
```

---

### Task 2: Implement the shared Windows launcher and thin batch entrypoints

**Files:**
- Create: `scripts/windows/setup_and_run.ps1`
- Create: `Играть.bat`
- Create: `Играть_системный_режим.bat`
- Create: `Сбросить_мир.bat`
- Test: `tests/test_windows_launcher.py`

**Interfaces:**
- Consumes: `-Action PlayFounder|PlaySystems|ResetSave`, repository root inferred from script location, optional `SAM_SEBE_OLLAMA_MODEL`, optional `SAM_SEBE_OLLAMA_URL`.
- Produces: repository-local `.venv`, `playtests/` directory, exact `sam-sebe-rpg` CLI process invocation, or a non-zero exit with a Russian actionable message.

- [ ] **Step 1: Implement batch wrappers**

Each `.bat` must follow this pattern, changing only the `-Action` value:

```bat
@echo off
setlocal
set "ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%ROOT%scripts\windows\setup_and_run.ps1" -Action PlayFounder
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Запуск завершился с ошибкой. Код: %EXIT_CODE%
  pause
)
exit /b %EXIT_CODE%
```

Use `PlaySystems` and `ResetSave` in the other two files.

- [ ] **Step 2: Implement parameter and repository path resolution**

PowerShell header:

```powershell
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("PlayFounder", "PlaySystems", "ResetSave")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$VenvDir = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvGame = Join-Path $VenvDir "Scripts\sam-sebe-rpg.exe"
$PlaytestsDir = Join-Path $RepoRoot "playtests"
$FounderDb = Join-Path $PlaytestsDir "founder-free.db"
$SystemsDb = Join-Path $PlaytestsDir "founder-systems.db"
```

- [ ] **Step 3: Implement compatible Python discovery**

`Find-CompatiblePython` must probe, in order:

```text
py -3.12
python
python3
```

For each candidate, run a Python one-liner that prints `major.minor`; accept only >= 3.12. Return a small object containing executable and prefix arguments, so `py -3.12` can be represented without string-eval.

If no candidate qualifies, print in Russian that Python 3.12+ is required and return exit code 10 without creating `.venv`.

- [ ] **Step 4: Implement idempotent `.venv` setup**

`Ensure-Venv`:

1. if `$VenvPython` exists, probe its version and reuse it only when >= 3.12;
2. otherwise remove only the invalid repository-local `$VenvDir` after informing the user;
3. create a new environment using `-m venv $VenvDir` through the selected compatible interpreter;
4. verify `$VenvPython` exists.

- [ ] **Step 5: Implement editable runtime installation**

`Ensure-GameInstalled` must run from `$RepoRoot`:

```powershell
& $VenvPython -m pip install -e .
```

Installation is required when `$VenvGame` is missing or when `.venv\.sam-sebe-launcher-version` does not contain launcher contract version `1`.

After a successful install, write `1` to that stamp. Do not upgrade pip and do not install developer extras.

- [ ] **Step 6: Implement Ollama discovery and local model selection**

`Get-OllamaModels`:

1. use `Get-Command ollama -ErrorAction SilentlyContinue`;
2. return an empty array if unavailable;
3. execute `ollama list`;
4. skip the header row and parse the first whitespace-separated column as model names;
5. return unique non-empty names.

`Resolve-FounderModel`:

1. if `SAM_SEBE_OLLAMA_MODEL` is set, require an exact match in the local list; if absent, explain and return `$null` rather than substituting silently;
2. with exactly one local model, return it;
3. with multiple models, print a numbered menu and accept only an in-range integer from `Read-Host`;
4. with zero models, return `$null`.

No download command may exist in the script.

- [ ] **Step 7: Implement game start and founder fallback**

`Start-Game` must ensure `playtests/` exists and use exact arguments rather than command-string evaluation.

Systems:

```powershell
& $VenvGame --mode systems --db $SystemsDb
```

Founder with model:

```powershell
$args = @("--mode", "founder", "--db", $FounderDb, "--ollama-model", $Model)
if ($env:SAM_SEBE_OLLAMA_URL) {
    $args += @("--ollama-url", $env:SAM_SEBE_OLLAMA_URL)
}
& $VenvGame @args
```

When no founder model is usable, explain that free input requires an already-installed Ollama model and ask:

```text
Запустить системный режим сейчас? [Y/N]
```

Only `Y`/`y` launches systems mode. Any other input exits without modifying a save.

- [ ] **Step 8: Implement safe save reset**

`Reset-PlaytestSave` lists only:

```text
1. playtests/founder-free.db
2. playtests/founder-systems.db
3. отмена
```

After choosing 1 or 2, display the exact path and require the user to type uppercase `DELETE`. Only then call `Remove-Item -LiteralPath <known path> -Force` if the file exists.

- [ ] **Step 9: Wire action dispatch and error codes**

Top-level action behavior:

```text
ResetSave   -> Reset-PlaytestSave, no Python/Ollama bootstrap
PlaySystems -> Python -> venv -> install -> Start-Game systems
PlayFounder -> Python -> venv -> install -> Ollama/model -> founder or explicit systems fallback
```

Catch unexpected exceptions once at top level, print stage/error in Russian, and exit non-zero. Propagate the game process `$LASTEXITCODE` when available.

- [ ] **Step 10: Run focused launcher tests and verify GREEN**

Run:

```bash
python -m pytest -q tests/test_windows_launcher.py
```

Expected: PASS.

- [ ] **Step 11: Commit implementation**

```bash
git add Играть.bat Играть_системный_режим.bat Сбросить_мир.bat scripts/windows/setup_and_run.ps1 tests/test_windows_launcher.py
git commit -m "feat: add Windows double-click launcher"
```

---

### Task 3: Document the actual play path

**Files:**
- Modify: `README.md`
- Test: `tests/test_windows_launcher.py`

**Interfaces:**
- Consumes: launcher filenames and behavior from Task 2.
- Produces: one obvious Windows playtest path for Ren and retained manual CLI instructions for debugging.

- [ ] **Step 1: Add a Windows quick-start section before manual environment setup**

Document exactly:

```text
Windows, обычная игра:
1. скачать/открыть ветку проекта;
2. дважды нажать Играть.bat;
3. если Python 3.12+ отсутствует — установить его и повторить;
4. если Ollama/локальная модель отсутствует — launcher ничего не устанавливает сам и предлагает systems mode.

Технический запуск:
Играть_системный_режим.bat

Сброс тестового мира:
Сбросить_мир.bat
```

State clearly that Ollama and models are external prerequisites for founder free-input and are never downloaded by the launcher.

- [ ] **Step 2: Keep the existing manual CLI section**

Do not delete the current `python -m venv`, `pip install`, `sam-sebe-rpg --mode ...` documentation; label it as manual/developer launch.

- [ ] **Step 3: Run focused tests**

```bash
python -m pytest -q tests/test_windows_launcher.py
```

Expected: PASS.

- [ ] **Step 4: Commit documentation**

```bash
git add README.md
git commit -m "docs: add Windows play launcher instructions"
```

---

### Task 4: Full regression and CI gate

**Files:**
- No new files expected.

**Interfaces:**
- Consumes: complete branch after Tasks 1-3.
- Produces: evidence that launcher additions did not regress the gameplay pilot.

- [ ] **Step 1: Run compile gate**

```bash
python -m compileall -q src scripts
```

Expected: PASS.

- [ ] **Step 2: Run full pytest suite**

```bash
python -m pytest -q
```

Expected: all tests PASS, including `tests/test_windows_launcher.py`.

- [ ] **Step 3: Verify GitHub Actions on the final head**

Confirm the `Pilot CI` workflow completes successfully on the exact final branch SHA.

- [ ] **Step 4: Inspect PR state without merging**

Confirm PR #1 remains open and unmerged. Do not merge without Ren's explicit request.

---

## Self-review

- Spec coverage: every launcher, Python bootstrap, Ollama policy, save safety, fallback, documentation, and regression requirement maps to a task above.
- Placeholder scan: no `TBD`, `TODO`, or unspecified error-handling steps remain.
- Type/interface consistency: action names are exactly `PlayFounder`, `PlaySystems`, `ResetSave`; save filenames are consistently `founder-free.db` and `founder-systems.db`; launcher contract version is consistently `1`.
- Scope check: no packaging, external installer, gameplay changes, or deployment work is included.