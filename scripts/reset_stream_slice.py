from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STREAM_DB = (PROJECT_ROOT / "data" / "stream-slice.sqlite3").resolve()


def stream_db_files(
    db_path: str | Path = STREAM_DB,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> tuple[Path, Path, Path]:
    root = Path(project_root).resolve()
    expected = (root / "data" / "stream-slice.sqlite3").resolve()
    candidate = Path(db_path).resolve()
    if candidate != expected:
        raise ValueError(
            f"refusing to reset anything except {expected}; received {candidate}"
        )
    return (
        expected,
        Path(f"{expected}-wal").resolve(),
        Path(f"{expected}-shm").resolve(),
    )


def reset_stream_slice(
    db_path: str | Path = STREAM_DB,
    *,
    project_root: str | Path = PROJECT_ROOT,
) -> list[Path]:
    deleted: list[Path] = []
    for path in stream_db_files(db_path, project_root=project_root):
        if path.exists():
            if not path.is_file():
                raise ValueError(f"refusing to delete non-file stream path: {path}")
            path.unlink()
            deleted.append(path)
    return deleted


def main() -> None:
    deleted = reset_stream_slice()
    if deleted:
        print("Stream Slice reset:")
        for path in deleted:
            print(f"  deleted {path.relative_to(PROJECT_ROOT)}")
    else:
        print("Stream Slice reset: database was already clean.")


if __name__ == "__main__":
    main()
