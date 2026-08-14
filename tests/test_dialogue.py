from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    return db, game


def test_neutral_mira_dialogue_uses_activity_and_renderer_is_read_only(tmp_path):
    db, game = make_game(tmp_path)
    player = game.register_player("dialogue-mira", "Ren")
    result = game.execute(
        CanonicalAction(player, ActionType.TALK, target_id="npc_mira", source_text="Мира, как дела?"),
        external_id="dialogue-mira-talk",
    )
    with db.connect() as conn:
        before_events = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        before_relation = tuple(conn.execute(
            "SELECT familiarity, trust, affinity, conflict FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
            (player,),
        ).fetchone())

    text = DialogueService(game).render(player, result)

    with db.connect() as conn:
        after_events = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
        after_relation = tuple(conn.execute(
            "SELECT familiarity, trust, affinity, conflict FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
            (player,),
        ).fetchone())
    assert before_events == after_events
    assert before_relation == after_relation == (1, 0, 0, 0)
    assert "**Мира**" in text
    assert "верстак" in text


def test_oren_dialogue_becomes_warm_after_food_gift(tmp_path):
    _, game = make_game(tmp_path)
    player = game.register_player("dialogue-warm", "Ren")
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="bread_1")).success
    assert game.execute(CanonicalAction(player, ActionType.GIVE, item_id="bread_1", target_id="npc_oren")).success
    talk = game.execute(
        CanonicalAction(player, ActionType.TALK, target_id="npc_oren", source_text="Орен, как дела?"),
        external_id="dialogue-warm-talk",
    )
    text = DialogueService(game).render(player, talk)
    assert "**Орен**" in text
    assert "смягча" in text.casefold()


def test_oren_dialogue_becomes_guarded_after_witnessed_sign_damage(tmp_path):
    _, game = make_game(tmp_path)
    player = game.register_player("dialogue-conflict", "Ren")
    assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
    assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
    assert game.execute(CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign")).success
    talk = game.execute(
        CanonicalAction(player, ActionType.TALK, target_id="npc_oren", source_text="Ну что, поговорим?"),
        external_id="dialogue-conflict-talk",
    )
    text = DialogueService(game).render(player, talk)
    assert "**Орен**" in text
    assert "насторож" in text.casefold() or "шум" in text.casefold()


def test_discord_replayed_talk_returns_same_dialogue_without_second_relation_change(tmp_path):
    db, game = make_game(tmp_path)
    app = DiscordGameApplication(game)
    first = app.handle_act("dialogue-replay", "Ren", "сказать npc_mira привет", "same-talk-interaction")
    second = app.handle_act("dialogue-replay", "Ren", "сказать npc_mira привет", "same-talk-interaction")
    assert first == second
    assert "**Мира**" in first
    with db.connect() as conn:
        player = conn.execute("SELECT actor_id FROM players WHERE discord_user_id='dialogue-replay'").fetchone()[0]
        familiarity = conn.execute(
            "SELECT familiarity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
            (player,),
        ).fetchone()[0]
        talk_events = conn.execute("SELECT COUNT(*) FROM action_events WHERE action_type='TALK'").fetchone()[0]
    assert familiarity == 1
    assert talk_events == 1
