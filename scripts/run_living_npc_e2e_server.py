from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService


E2E_NOW = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def build_living_npc_e2e_app(db_path: str | Path | None = None):
    path = Path(db_path or os.environ.get("SAM_SEBE_DB", "data/e2e-living-npc.sqlite3"))
    db = GameDatabase(path)
    db.initialize()
    clock = FakeClock(E2E_NOW)
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=None)
    return create_app(game, quest, dialogue)


def main() -> None:
    uvicorn.run(build_living_npc_e2e_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
