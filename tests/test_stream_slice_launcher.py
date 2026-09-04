from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts.reset_stream_slice import reset_stream_slice, stream_db_files
from scripts.run_stream_slice import STREAM_DB, STREAM_NOW, build_stream_slice_app


def test_stream_launcher_uses_isolated_db_and_fixed_evening_clock() -> None:
    assert STREAM_DB.as_posix().endswith("data/stream-slice.sqlite3")
    assert STREAM_DB.name == "stream-slice.sqlite3"
    assert STREAM_NOW == datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def test_stream_launcher_builds_with_explicit_offline_provider(tmp_path: Path) -> None:
    db_path = tmp_path / "stream-slice.sqlite3"
    app = build_stream_slice_app(db_path, provider=None)
    assert app is not None
    assert db_path.exists()


def test_stream_db_files_are_exactly_db_wal_and_shm(tmp_path: Path) -> None:
    project_root = tmp_path
    db_path = project_root / "data" / "stream-slice.sqlite3"
    expected = {
        (project_root / "data" / "stream-slice.sqlite3").resolve(),
        (project_root / "data" / "stream-slice.sqlite3-wal").resolve(),
        (project_root / "data" / "stream-slice.sqlite3-shm").resolve(),
    }
    assert set(stream_db_files(db_path, project_root=project_root)) == expected


@pytest.mark.parametrize(
    "relative",
    [
        "data/world.sqlite3",
        "data/e2e-stream-slice.sqlite3",
        "stream-slice.sqlite3",
        "other/stream-slice.sqlite3",
    ],
)
def test_reset_rejects_any_path_outside_exact_stream_db(tmp_path: Path, relative: str) -> None:
    with pytest.raises(ValueError):
        stream_db_files(tmp_path / relative, project_root=tmp_path)


def test_reset_deletes_only_stream_db_and_sidecars(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "stream-slice.sqlite3"
    targets = [db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")]
    for target in targets:
        target.write_text("stream", encoding="utf-8")
    keep = data_dir / "world.sqlite3"
    keep.write_text("keep", encoding="utf-8")

    deleted = reset_stream_slice(db_path, project_root=tmp_path)

    assert {path.resolve() for path in deleted} == {path.resolve() for path in targets}
    assert all(not path.exists() for path in targets)
    assert keep.read_text(encoding="utf-8") == "keep"
