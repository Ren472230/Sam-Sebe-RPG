from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import (
    DialogueDecision,
    DialogueService,
    OpenAIResponsesProvider,
)
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.quest import QuestService


class RecordingProvider:
    def __init__(self, decision) -> None:
        self.decision = decision
        self.context = None

    def generate(self, context):
        self.context = context
        return self.decision


class FailingProvider:
    def generate(self, context):
        raise RuntimeError("provider down")


def make_services(tmp_path: Path, provider=None):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=provider)
    player = game.register_player("local-a", "Ren")
    return db, game, quest, dialogue, player


def test_dialogue_context_reads_role_quest_and_relation_without_mutating(tmp_path: Path) -> None:
    provider = RecordingProvider(
        DialogueDecision(
            text="Дрова у меня почти кончились.",
            proposal="offer_quest:bring_5_firewood",
        )
    )
    db, _, _, dialogue, player = make_services(tmp_path, provider)

    decision = dialogue.talk(player, "Есть работа?")

    assert decision.text == "Дрова у меня почти кончились."
    assert decision.proposal == "offer_quest:bring_5_firewood"
    assert decision.used_fallback is False
    assert provider.context is not None
    assert provider.context.npc_id == "npc_oren"
    assert provider.context.role == "innkeeper"
    assert provider.context.location_id == "tavern_interior"
    assert provider.context.quest.status == "available"
    assert provider.context.trust == 0
    assert provider.context.memories == ()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM quests").fetchone()[0] == 0


def test_invalid_llm_proposal_forces_deterministic_fallback(tmp_path: Path) -> None:
    provider = RecordingProvider(
        DialogueDecision(text="Идём грабить банк.", proposal="give_1000_coins")
    )
    _, _, _, dialogue, player = make_services(tmp_path, provider)

    decision = dialogue.talk(player, "Что делать?")

    assert decision.used_fallback is True
    assert decision.proposal == "offer_quest:bring_5_firewood"
    assert "дров" in decision.text.lower()
    assert "банк" not in decision.text.lower()


def test_state_invalid_offer_proposal_forces_fallback(tmp_path: Path) -> None:
    provider = RecordingProvider(
        DialogueDecision(
            text="Ещё раз возьми тот же квест.",
            proposal="offer_quest:bring_5_firewood",
        )
    )
    _, _, quest, dialogue, player = make_services(tmp_path, provider)
    assert quest.accept(player).success

    decision = dialogue.talk(player, "Что дальше?")

    assert decision.used_fallback is True
    assert decision.proposal is None
    assert "пять" in decision.text.lower() or "5" in decision.text


def test_malformed_provider_response_forces_fallback(tmp_path: Path) -> None:
    provider = RecordingProvider(SimpleNamespace(text="broken-without-proposal"))
    _, _, _, dialogue, player = make_services(tmp_path, provider)

    decision = dialogue.talk(player, "Привет")

    assert decision.used_fallback is True
    assert decision.proposal == "offer_quest:bring_5_firewood"


def test_provider_failure_returns_quest_aware_fallback(tmp_path: Path) -> None:
    _, _, quest, dialogue, player = make_services(tmp_path, FailingProvider())

    available = dialogue.talk(player, "Привет")
    assert available.used_fallback is True
    assert available.proposal == "offer_quest:bring_5_firewood"
    assert "дров" in available.text.lower()

    assert quest.accept(player).success
    active = dialogue.talk(player, "Напомни")
    assert active.used_fallback is True
    assert active.proposal is None
    assert "пять" in active.text.lower() or "5" in active.text


def test_completed_quest_memory_and_trust_enter_dialogue_context(tmp_path: Path) -> None:
    provider = RecordingProvider(DialogueDecision(text="Теперь я тебя помню."))
    db, game, quest, dialogue, player = make_services(tmp_path, provider)
    assert quest.accept(player).success
    for index in range(1, 6):
        assert game.execute(
            CanonicalAction(
                actor_id=player,
                action_type=ActionType.TAKE,
                target_id=f"firewood_{index}",
            )
        ).success
    assert quest.turn_in(player).success

    dialogue.talk(player, "Ну как?")

    assert provider.context.quest.status == "completed"
    assert provider.context.trust == 10
    assert provider.context.memories == (
        "The player brought Oren the requested firewood.",
    )
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM npc_memories").fetchone()[0] == 1


def test_openai_provider_requests_strict_structured_output() -> None:
    captured = {}

    class FakeResponses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text='{"text":"Принеси пять поленьев.","proposal":"offer_quest:bring_5_firewood"}'
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    provider = OpenAIResponsesProvider(client=fake_client, model="gpt-5")
    context = SimpleNamespace(to_prompt=lambda: "STATE\nUSER:Есть работа?")

    decision = provider.generate(context)

    assert decision.proposal == "offer_quest:bring_5_firewood"
    assert captured["model"] == "gpt-5"
    assert captured["text"]["format"]["type"] == "json_schema"
    assert captured["text"]["format"]["strict"] is True
