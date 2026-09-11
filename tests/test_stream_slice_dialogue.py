from __future__ import annotations

from datetime import datetime, timezone

import openai

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService, OpenAIResponsesProvider
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService
from samseberpg.social_world import SocialWorldService


EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)


def _services(tmp_path, key: str, *, provider=None):
    db = GameDatabase(tmp_path / f"{key}.sqlite3")
    db.initialize()
    clock = FakeClock(EVENING)
    game = GameService(
        db,
        clock,
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    player_id = game.register_player(key, "Stream Player")
    dialogue = DialogueService(db, QuestService(db, clock), provider=provider)
    return db, game, dialogue, player_id


def _move(game: GameService, player_id: str, destination_id: str) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.MOVE,
            destination_id=destination_id,
        )
    )
    assert result.success is True


def _wait_for_arrival(game: GameService, player_id: str) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 10},
        ),
        external_id="stream-dialogue-wait-10",
    )
    assert result.success is True


def _move_to_tavern(game: GameService, player_id: str) -> None:
    _move(game, player_id, "village_square")
    _move(game, player_id, "tavern_interior")


def _deliver_bread(game: GameService, player_id: str) -> None:
    _move(game, player_id, "village_square")
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="bread_loaf_1",
        )
    )
    assert taken.success is True
    _move(game, player_id, "tavern_interior")
    given = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="bread_loaf_1",
            recipient_id="npc_oren",
        )
    )
    assert given.success is True


def test_talen_fallback_tells_persisted_road_news(tmp_path) -> None:
    _, game, dialogue, player_id = _services(tmp_path, "talen-news")
    _wait_for_arrival(game, player_id)
    _move_to_tavern(game, player_id)

    decision = dialogue.talk(
        player_id,
        "Что случилось в дороге?",
        npc_id="npc_wayfarer_1",
    )

    text = decision.text.lower()
    assert decision.used_fallback is True
    assert "восточн" in text
    assert "караван" in text


def test_oren_fallback_reports_talens_news_with_source(tmp_path) -> None:
    _, game, dialogue, player_id = _services(tmp_path, "oren-news")
    _wait_for_arrival(game, player_id)
    _move_to_tavern(game, player_id)

    decision = dialogue.talk(
        player_id,
        "Что рассказал Тален?",
        npc_id="npc_oren",
    )

    text = decision.text.lower()
    assert decision.used_fallback is True
    assert "тален" in text
    assert "восточн" in text
    assert "караван" in text


def test_oren_fallback_requests_then_acknowledges_bread(tmp_path) -> None:
    _, game, dialogue, player_id = _services(tmp_path, "oren-bread")
    _wait_for_arrival(game, player_id)
    _move_to_tavern(game, player_id)

    before = dialogue.talk(
        player_id,
        "Нужна помощь с гостем?",
        npc_id="npc_oren",
    )
    assert before.used_fallback is True
    assert "хлеб" in before.text.lower()

    _deliver_bread(game, player_id)
    after = dialogue.talk(
        player_id,
        "Хлеб подошёл?",
        npc_id="npc_oren",
    )
    assert after.used_fallback is True
    assert any(token in after.text.lower() for token in ("спасибо", "гост", "хлеб"))


def test_provider_timeout_falls_back_to_talens_grounded_news(tmp_path) -> None:
    class TimeoutProvider:
        def generate(self, context):
            raise TimeoutError("stream provider timeout")

    _, game, dialogue, player_id = _services(
        tmp_path,
        "provider-timeout",
        provider=TimeoutProvider(),
    )
    _wait_for_arrival(game, player_id)
    _move_to_tavern(game, player_id)

    decision = dialogue.talk(
        player_id,
        "Что случилось в дороге?",
        npc_id="npc_wayfarer_1",
    )

    assert decision.used_fallback is True
    assert "караван" in decision.text.lower()


def test_default_openai_provider_uses_stream_safe_timeout_and_retry(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    monkeypatch.setenv("OPENAI_API_KEY", "test-stream-key")

    provider = OpenAIResponsesProvider()

    assert provider.client is not None
    assert captured["api_key"] == "test-stream-key"
    assert captured["timeout"] == 8.0
    assert captured["max_retries"] == 1
