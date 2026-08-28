from __future__ import annotations

import os
from pathlib import Path

from .api import create_app
from .clock import SystemClock
from .db import GameDatabase
from .dialogue import DialogueService, OpenAIResponsesProvider
from .game import GameService
from .living_world import LivingWorldService
from .quest import QuestService


def build_app(db_path: str | Path = "data/world.sqlite3", *, provider=None):
    db = GameDatabase(db_path)
    db.initialize()
    clock = SystemClock()
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    if provider is None and os.environ.get("OPENAI_API_KEY"):
        provider = OpenAIResponsesProvider()
    dialogue = DialogueService(db, quest, provider=provider)
    return create_app(game, quest, dialogue)


def configured_db_path() -> str:
    return os.environ.get("SAM_SEBE_DB", "data/world.sqlite3")


def main() -> None:
    import uvicorn

    uvicorn.run(build_app(configured_db_path()), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
