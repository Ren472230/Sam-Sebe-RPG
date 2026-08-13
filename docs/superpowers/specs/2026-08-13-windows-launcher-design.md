# Windows Double-Click Launcher Design

**Date:** 2026-08-13

## Goal

Make the current Sam-Sebe-RPG Pilot playable on Ren's Windows PC by double-clicking a launcher in the repository root, without requiring the player to manually create a virtual environment, install the package, or remember CLI commands.

The launcher may prepare the Python environment for this repository. It must never silently install Ollama, download an Ollama model, modify system-wide Python, or make unrelated machine changes.

## Scope

This design targets one machine class only: a Windows PC running the repository checkout. It is not a portable ZIP, installer, Discord deployment, web build, or distribution package for external testers.

### In scope

- `Играть.bat` for the default founder-oriented launch path.
- `Играть_системный_режим.bat` for deterministic/system diagnostics.
- `Сбросить_мир.bat` for an explicit save reset with confirmation.
- `scripts/windows/setup_and_run.ps1` as the shared launcher implementation.
- Automatic repository-local `.venv` creation when needed.
- Automatic `pip install -e .` into that `.venv` when needed.
- Python 3.12+ detection with an actionable failure message.
- Ollama availability detection without installing it.
- Detection of already-installed Ollama models without downloading one.
- Persistent saves under `playtests/`.
- Clear exit/error messages that remain visible when launched by double-click.
- Automated launcher contract tests runnable on CI without needing Windows GUI interaction or a real Ollama server.

### Out of scope

- Installing Python automatically.
- Installing Ollama automatically.
- Pulling/downloading Ollama models automatically.
- Editing PATH, PowerShell execution policy, registry, firewall, services, or Windows Terminal settings.
- Creating a `.exe`, MSI, portable ZIP, desktop shortcut, Discord bot, hosted server, or web UI.
- Changing gameplay rules or free-input parser semantics.

## User experience

### First launch: `Играть.bat`

The batch file invokes the shared PowerShell launcher using a process-scoped bypass so the user does not have to change machine execution policy:

```text
double-click Играть.bat
  -> resolve repository root
  -> find Python 3.12+
  -> create .venv if absent
  -> install/update editable project in .venv if required
  -> ensure playtests/ exists
  -> detect Ollama
       -> Ollama unavailable: explain that founder free-input needs Ollama and offer systems-mode launch
       -> Ollama available: inspect locally installed models
            -> configured model installed: use it
            -> exactly one model installed: use it
            -> multiple models installed: show numbered local-only selection
            -> zero models installed: explain how to install/pull one manually and offer systems mode
  -> launch sam-sebe-rpg --mode founder when a usable local model exists
  -> otherwise launch systems mode only after explicit user choice
```

The founder save path is:

```text
playtests/founder-free.db
```

The systems save path is:

```text
playtests/founder-systems.db
```

### Subsequent launch

If `.venv` is healthy and the package is installed, startup skips environment creation. The launcher should be idempotent: repeated starts do not create duplicate environments or reset saves.

### Systems launcher

`Играть_системный_режим.bat` skips Ollama discovery and starts:

```text
sam-sebe-rpg --mode systems --db playtests/founder-systems.db
```

This gives a guaranteed gameplay path even before Ollama is installed.

### Save reset

`Сбросить_мир.bat` must never delete a save immediately. It asks which known playtest save to remove and requires an explicit confirmation before deletion. It does not delete arbitrary paths and does not touch source files.

## Architecture

### Thin `.bat` entrypoints

The root batch files only:

1. calculate `%~dp0` as repository root;
2. invoke `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\windows\setup_and_run.ps1` with a mode argument;
3. preserve the resulting exit code;
4. pause only on failure so a double-clicked error window does not disappear.

No setup logic is duplicated across batch files.

### PowerShell launcher

`scripts/windows/setup_and_run.ps1` owns orchestration. It exposes small internal functions with one responsibility each:

- `Find-CompatiblePython` — return a command descriptor for Python >= 3.12 or `$null`.
- `Ensure-Venv` — create/validate `.venv` using the compatible interpreter.
- `Ensure-GameInstalled` — install the local project editable into `.venv` when the console script is unavailable or project metadata changed.
- `Get-OllamaModels` — inspect `ollama list` output only when `ollama` is present.
- `Resolve-FounderModel` — choose a configured/unique/user-selected already-installed model; never download.
- `Start-Game` — launch the `.venv` console script with exact mode/database/model arguments.
- `Reset-PlaytestSave` — restrict deletion to the two known playtest database paths and ask for explicit confirmation.

The script accepts:

```text
-Action PlayFounder | PlaySystems | ResetSave
```

Optional environment configuration:

```text
SAM_SEBE_OLLAMA_MODEL=<already installed local model>
SAM_SEBE_OLLAMA_URL=http://localhost:11434
```

The existing CLI remains the authoritative application entrypoint.

## Python discovery

Detection order:

1. `py -3.12`
2. `python`
3. `python3`

A candidate is accepted only after executing a version probe and confirming `major > 3` or `major == 3 and minor >= 12`.

If no compatible interpreter exists, the launcher prints:

- that Python 3.12+ is required;
- that nothing was installed or changed;
- the exact next action: install Python 3.12+ and rerun `Играть.bat`.

The launcher must not fall back to an incompatible Python.

## Environment installation policy

The environment is repository-local:

```text
.venv/
```

Installation command:

```text
.venv\Scripts\python.exe -m pip install -e .
```

Developer-only dependencies are not required for playing and therefore the launcher does not install `.[dev]`.

A small stamp file under `.venv/` may record the launcher/install contract version. The launcher reinstalls editable metadata when the console entrypoint is missing or the stamp version does not match. It does not run a network-heavy upgrade on every launch.

## Ollama policy

Ollama is optional for running the game but required for the intended founder free-input experiment.

The launcher may execute only read/start-oriented commands against an already installed Ollama setup, such as detecting the executable and listing local models. It does not run package managers or `ollama pull`.

Model resolution order:

1. `SAM_SEBE_OLLAMA_MODEL` if set and present in the local model list;
2. the only locally installed model if exactly one exists;
3. interactive numbered selection if multiple local models exist;
4. no founder launch if no usable local model exists.

When founder mode cannot start because Ollama/model is missing, the launcher offers systems mode so the user can still play and inspect the current build.

## Error handling

All setup failures are fail-closed:

- no compatible Python -> no environment mutation;
- venv creation failure -> no attempt to run global `sam-sebe-rpg`;
- editable install failure -> no game launch;
- configured Ollama model missing -> do not silently substitute unless the user selects another installed model;
- game process exit code is propagated to the batch entrypoint.

Messages are written in Russian and include the failed stage plus the next useful action.

## Data safety

- Saves live only under `playtests/`.
- Normal launch never deletes or recreates an existing save.
- Reset supports only `founder-free.db` and `founder-systems.db`.
- Reset requires explicit confirmation.
- Launcher setup modifies only `.venv/`, `playtests/`, and normal Python package metadata inside `.venv`.

## Testing strategy

Windows shell behavior is split into pure/testable decisions and thin process calls.

CI tests should verify at minimum:

1. the three root `.bat` entrypoints exist and delegate to one PowerShell script;
2. launchers use repository-relative paths rather than hard-coded user paths;
3. PowerShell script has the three declared actions;
4. Python version policy is >= 3.12;
5. playing installs only `-e .`, not `.[dev]`;
6. founder and systems database paths are distinct and under `playtests/`;
7. no launcher source contains automatic Ollama install/download commands such as `winget install`, `choco install`, `ollama pull`, or equivalent;
8. reset code is restricted to the known save names and contains a confirmation gate;
9. existing Python gameplay test suite remains green.

Because GitHub CI currently runs on Ubuntu, tests must inspect launcher contracts as text/structure and keep OS-specific orchestration thin. A later Windows CI matrix is optional and not required for this personal MVP.

## Success criteria

The feature is complete when, on a Windows checkout with Python 3.12+:

- double-clicking `Играть_системный_режим.bat` can bootstrap `.venv` and start a persistent systems-mode game;
- double-clicking `Играть.bat` starts founder mode when an already-installed Ollama model is available;
- missing Ollama/model never triggers a hidden install and leaves a usable systems-mode fallback;
- restarting preserves the previous save;
- save reset is explicit and scoped;
- full repository CI remains green.

## YAGNI boundary

Do not add packaging/distribution infrastructure until a real founder playtest demonstrates that the current game deserves an external tester build. The next product evidence should come from playing this local launcher build, not from building deployment machinery.