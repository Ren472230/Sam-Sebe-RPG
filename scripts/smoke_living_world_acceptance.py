from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str]) -> int:
    print("$", " ".join(command), flush=True)
    completed = subprocess.run(command, cwd=ROOT, check=False)
    return int(completed.returncode)


def main() -> int:
    gates = [
        [sys.executable, "-m", "pytest", "-q"],
        [sys.executable, "scripts/smoke_vertical_slice.py"],
    ]
    for command in gates:
        code = _run(command)
        if code != 0:
            print("LIVING WORLD ACCEPTANCE: FAIL", flush=True)
            return code
    print("LIVING WORLD ACCEPTANCE: PASS", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
