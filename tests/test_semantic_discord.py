from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.game import GameService
from samseberpg.intent import IntentProposal, IntentResolutionError


class RecordingResolver:
    def __init__(self, proposals):
        self.proposals = proposals
        self.calls = []

    def resolve(self, text, context):
        self.calls.append((text, context))
        proposal = self.proposals[text]
        if isinstance(proposal, Exception):
            raise proposal
        return proposal


def make_app(tmp_path, resolver):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    return db, DiscordGameApplication(game, intent_resolver=resolver)


def test_exact_parser_takes_precedence_and_does_not_call_semantic_resolver(tmp_path):
    resolver = RecordingResolver({})
    db, app = make_app(tmp_path, resolver)

    text = app.handle_act("discord-a", "Ren", "взять stone_flat_1", "exact-take")

    assert "Вы берёте" in text
    assert resolver.calls == []
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1


def test_semantic_resolver_can_drive_natural_take_move_throw_buy_and_use(tmp_path):
    resolver = RecordingResolver(
        {
            "подберу плоский камень": IntentProposal("TAKE", None, "stone_flat_1", None, "take stone"),
            "пойду к таверне": IntentProposal("MOVE", None, None, "village_square", "move square"),
            "швырну камень в вывеску": IntentProposal("THROW", "stone_flat_1", "tavern_sign", None, "damage sign"),
            "куплю бутылку у трактирщика": IntentProposal("BUY", "bottle_1", "npc_oren", None, "buy bottle"),
            "наберу воды в бутылку": IntentProposal("USE", "bottle_1", "village_well", None, "fill bottle"),
        }
    )
    db, app = make_app(tmp_path, resolver)

    assert "Вы берёте Плоский камень" in app.handle_act(
        "discord-a", "Ren", "подберу плоский камень", "nl-take"
    )
    assert "переходите" in app.handle_act(
        "discord-a", "Ren", "пойду к таверне", "nl-move"
    )
    assert "Состояние цели: 80%" in app.handle_act(
        "discord-a", "Ren", "швырну камень в вывеску", "nl-throw"
    )
    assert "покупаете Пустая бутылка" in app.handle_act(
        "discord-a", "Ren", "куплю бутылку у трактирщика", "nl-buy"
    )
    assert "наполняете Пустая бутылка водой" in app.handle_act(
        "discord-a", "Ren", "наберу воды в бутылку", "nl-use"
    )

    with db.connect() as conn:
        assert conn.execute("SELECT coins FROM players").fetchone()[0] == 7
        assert conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE success = 1"
        ).fetchone()[0] == 5
    assert [call[0] for call in resolver.calls] == [
        "подберу плоский камень",
        "пойду к таверне",
        "швырну камень в вывеску",
        "куплю бутылку у трактирщика",
        "наберу воды в бутылку",
    ]


def test_hallucinated_semantic_id_is_rejected_without_gameplay_event(tmp_path):
    resolver = RecordingResolver(
        {
            "уйду в замок": IntentProposal(
                "MOVE", None, None, "secret_castle", "hallucinated location"
            )
        }
    )
    db, app = make_app(tmp_path, resolver)

    text = app.handle_act("discord-a", "Ren", "уйду в замок", "nl-hallucination")

    assert "не удалось" in text.casefold() or "не понял" in text.casefold()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 0
        player = conn.execute("SELECT actor_id FROM players").fetchone()[0]
        assert conn.execute(
            "SELECT location_id FROM actors WHERE id = ?", (player,)
        ).fetchone()[0] == "workshop_yard"


def test_semantic_provider_failure_does_not_create_event_or_mutate_gameplay_state(tmp_path):
    resolver = RecordingResolver(
        {"что-нибудь сделай": IntentResolutionError("ollama unavailable")}
    )
    db, app = make_app(tmp_path, resolver)

    text = app.handle_act("discord-a", "Ren", "что-нибудь сделай", "nl-error")

    assert "не удалось" in text.casefold()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM processed_interactions").fetchone()[0] == 0
