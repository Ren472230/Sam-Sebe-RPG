from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
DEFAULT_DB = ROOT / "data" / "playtest-world.sqlite3"
PLAYTEST_TIME = "2026-08-24T17:00:00+00:00"
BACKEND_HEALTH = "http://127.0.0.1:8000/api/health"
GAME_URL = "http://127.0.0.1:5173"


def reset_save(database: Path) -> None:
    for path in (database, Path(f"{database}-wal"), Path(f"{database}-shm")):
        path.unlink(missing_ok=True)


def _version(command: str) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    completed = subprocess.run(
        [executable, "--version"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return (completed.stdout or completed.stderr).strip()


def preflight() -> tuple[bool, list[str]]:
    messages: list[str] = []
    ok = True

    if sys.version_info < (3, 12):
        ok = False
        messages.append(f"[FAIL] Python {sys.version.split()[0]} — нужен Python 3.12+")
    else:
        messages.append(f"[OK] Python {sys.version.split()[0]}")

    node_version = _version("node")
    if node_version is None:
        ok = False
        messages.append("[FAIL] Node.js не найден — нужен Node.js 22+")
    else:
        messages.append(f"[OK] Node.js {node_version}")

    npm_version = _version("npm")
    if npm_version is None:
        ok = False
        messages.append("[FAIL] npm не найден")
    else:
        messages.append(f"[OK] npm {npm_version}")

    if not (ROOT / "pyproject.toml").is_file():
        ok = False
        messages.append("[FAIL] pyproject.toml не найден — запусти скрипт из репозитория Sam-Sebe-RPG")
    else:
        messages.append("[OK] Python-проект найден")

    if not (WEB_DIR / "package.json").is_file():
        ok = False
        messages.append("[FAIL] web/package.json не найден")
    else:
        messages.append("[OK] Браузерный проект найден")

    return ok, messages


def _run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("$", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Команда завершилась с кодом {completed.returncode}: {' '.join(command)}")


def ensure_dependencies() -> None:
    if importlib.util.find_spec("samseberpg") is None:
        print("Устанавливаю серверную часть...", flush=True)
        _run([sys.executable, "-m", "pip", "install", "-e", "."])

    if not (WEB_DIR / "node_modules").is_dir():
        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError("npm не найден")
        print("Устанавливаю зависимости браузерной части...", flush=True)
        _run([npm, "install", "--no-audit", "--no-fund"], cwd=WEB_DIR)


def _wait_for(url: str, process: subprocess.Popen[bytes], label: str, timeout: float = 45.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{label} завершился раньше готовности с кодом {process.returncode}")
        try:
            with urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return
        except (URLError, TimeoutError, OSError):
            time.sleep(0.2)
    raise RuntimeError(f"{label} не стал доступен: {url}")


def _start_process(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.Popen[bytes]:
    if os.name == "nt":
        return subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)


def _stop(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return

    if os.name == "nt":
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        return

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)


def launch(database: Path, *, open_browser: bool, smoke: bool = False) -> int:
    ensure_dependencies()
    database.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["SAM_SEBE_DB"] = str(database)
    env["SAM_SEBE_PLAYTEST_TIME"] = PLAYTEST_TIME
    env["OPENAI_API_KEY"] = ""

    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm не найден")

    backend: subprocess.Popen[bytes] | None = None
    frontend: subprocess.Popen[bytes] | None = None
    try:
        print(f"Сохранение: {database}", flush=True)
        print("Запускаю сервер...", flush=True)
        backend = _start_process(
            [sys.executable, "-m", "samseberpg.server"],
            cwd=ROOT,
            env=env,
        )
        _wait_for(BACKEND_HEALTH, backend, "Сервер")

        print("Запускаю браузерную игру...", flush=True)
        frontend = _start_process(
            [npm, "run", "dev", "--", "--host", "127.0.0.1"],
            cwd=WEB_DIR,
            env=env,
        )
        _wait_for(GAME_URL, frontend, "Браузерная игра")

        print("PLAYTEST READY", flush=True)
        if smoke:
            print("PLAYTEST LAUNCH SMOKE: PASS", flush=True)
            return 0

        print(f"Открой: {GAME_URL}", flush=True)
        print("Управление: WASD — движение, E — взаимодействие; панель Живого мира — наблюдение и вмешательство.", flush=True)
        print("Для остановки нажми Ctrl+C в этом окне.", flush=True)
        if open_browser:
            webbrowser.open(GAME_URL)

        while True:
            if backend.poll() is not None:
                raise RuntimeError(f"Сервер завершился с кодом {backend.returncode}")
            if frontend.poll() is not None:
                raise RuntimeError(f"Браузерная часть завершилась с кодом {frontend.returncode}")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Останавливаю игру...", flush=True)
        return 0
    finally:
        _stop(frontend)
        _stop(backend)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Простой запуск первой игровой проверки Сам-себе-RPG")
    parser.add_argument("--check", action="store_true", help="только проверить окружение; ничего не менять и не запускать")
    parser.add_argument("--reset", action="store_true", help="удалить только сохранение игрового теста перед запуском")
    parser.add_argument("--no-open", action="store_true", help="не открывать браузер автоматически")
    parser.add_argument("--smoke", action="store_true", help="поднять обе части, проверить готовность и сразу корректно остановить")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="путь к отдельному SQLite-сохранению игрового теста")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ok, messages = preflight()
    for message in messages:
        print(message)
    print(f"PLAYTEST PREFLIGHT: {'PASS' if ok else 'FAIL'}")
    if not ok:
        return 2
    if args.check:
        return 0

    database = args.db if args.db.is_absolute() else ROOT / args.db
    if args.reset:
        reset_save(database)
        print(f"Сохранение сброшено: {database}", flush=True)

    try:
        return launch(database, open_browser=not args.no_open, smoke=args.smoke)
    except Exception as exc:
        print(f"PLAYTEST START: FAIL — {exc}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
