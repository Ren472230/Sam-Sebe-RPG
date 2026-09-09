from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService, OpenAIResponsesProvider
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService
from samseberpg.social_world import SocialWorldService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STREAM_DB = (PROJECT_ROOT / "data" / "stream-slice.sqlite3").resolve()
STREAM_NOW = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)
_AUTO_PROVIDER = object()


def build_stream_slice_app(
    db_path: str | Path = STREAM_DB,
    *,
    provider=_AUTO_PROVIDER,
):
    path = Path(db_path)
    db = GameDatabase(path)
    db.initialize()
    clock = FakeClock(STREAM_NOW)
    game = GameService(
        db,
        clock,
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    quest = QuestService(db, clock)
    if provider is _AUTO_PROVIDER:
        provider = OpenAIResponsesProvider() if os.environ.get("OPENAI_API_KEY") else None
    dialogue = DialogueService(db, quest, provider=provider)
    return create_app(game, quest, dialogue)


def main() -> None:
    STREAM_DB.parent.mkdir(parents=True, exist_ok=True)
    print(f"Stream Slice backend database: {STREAM_DB.relative_to(PROJECT_ROOT)}")
    print("Stream Slice clock: 2026-08-24 17:00 UTC")
    uvicorn.run(build_stream_slice_app(), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
