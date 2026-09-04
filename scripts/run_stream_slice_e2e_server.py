from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from scripts.run_stream_slice import build_stream_slice_app


E2E_DB = Path("data/e2e-stream-slice.sqlite3")


def main() -> None:
    db_path = Path(os.environ.get("SAM_SEBE_DB", str(E2E_DB)))
    uvicorn.run(
        build_stream_slice_app(db_path, provider=None),
        host="127.0.0.1",
        port=8000,
    )


if __name__ == "__main__":
    main()
