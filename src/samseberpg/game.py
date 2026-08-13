from __future__ import annotations

import sqlite3

from .day import DayService
from .db import GameDatabase
from .game_base import GameService as _BaseGameService
from .living_world import LivingWorldService
from .social import SocialService


class _LivingDayService(DayService):
    def __init__(self, living_world: LivingWorldService):
        self.living_world = living_world

    def advance(self, conn: sqlite3.Connection, ticks: int, *, on_tick=None) -> int:
        return super().advance(
            conn,
            ticks,
            on_tick=on_tick or self.living_world.tick,
        )


class _StateAwareSocialService(SocialService):
    def __init__(self, db: GameDatabase):
        self.db = db

    def talk_summary(self, npc_id, trust, topic=None, *, state=None):
        if state is None:
            entity = self.db.fetch_entity(npc_id)
            state = entity["state"] if entity is not None else {}
        return super().talk_summary(npc_id, trust, topic, state=state)


class GameService(_BaseGameService):
    """Authoritative game service with deterministic Living World ticks attached."""

    def __init__(self, db: GameDatabase, seed: int = 0):
        super().__init__(db, seed=seed)
        self.living_world = LivingWorldService()
        self.day = _LivingDayService(self.living_world)
        self.social = _StateAwareSocialService(db)
