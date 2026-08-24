from __future__ import annotations

from samseberpg import server


def test_configured_db_path_prefers_environment(monkeypatch) -> None:
    monkeypatch.setenv("SAM_SEBE_DB", "data/e2e-world.sqlite3")

    assert server.configured_db_path() == "data/e2e-world.sqlite3"


def test_configured_db_path_defaults_to_runtime_save(monkeypatch) -> None:
    monkeypatch.delenv("SAM_SEBE_DB", raising=False)

    assert server.configured_db_path() == "data/world.sqlite3"
