from __future__ import annotations

from datetime import datetime, timezone

from samseberpg import server
from samseberpg.clock import FakeClock, SystemClock


def test_server_uses_system_clock_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SAM_SEBE_PLAYTEST_TIME", raising=False)

    clock = server.configured_clock()

    assert isinstance(clock, SystemClock)


def test_server_uses_fixed_clock_only_when_playtest_time_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("SAM_SEBE_PLAYTEST_TIME", "2026-08-24T17:00:00+00:00")

    clock = server.configured_clock()

    assert isinstance(clock, FakeClock)
    assert clock.now() == datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)
