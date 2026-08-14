from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    def __init__(self, current: datetime) -> None:
        self._current = _require_aware(current)

    def now(self) -> datetime:
        return self._current

    def set(self, current: datetime) -> None:
        self._current = _require_aware(current)

    def advance(self, delta: timedelta) -> None:
        self._current += delta


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("clock datetime must be timezone-aware")
    return value.astimezone(timezone.utc)
