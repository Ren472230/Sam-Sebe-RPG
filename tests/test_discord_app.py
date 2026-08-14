from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.game import GameService
from samseberpg.presentation import limit_message


def make_app(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    game = GameService(db, FakeClock(now))
    return db, DiscordGameApplication(game)


def test_look_registers_player_and_renders_shared_location(tmp_path):
    db, app = make_app(tmp_path)

    text = app.handle_look("discord-a", "Ren")

    assert "Двор мастерской" in text
    assert "Плоский камень" in text
    assert "Мира" in text
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 1


def test_act_take_updates_inventory_visible_in_me(tmp_path):
    _, app = make_app(tmp_path)

    result_text = app.handle_act(
        "discord-a",
        "Ren",
        "взять stone_flat_1",
        "interaction-take-1",
    )
    me_text = app.handle_me("discord-a", "Ren")

    assert "Вы берёте Плоский камень" in result_text
    assert "Плоский камень" in me_text


def test_duplicate_interaction_is_idempotent_through_discord_application(tmp_path):
    db, app = make_app(tmp_path)

    first = app.handle_act(
        "discord-a", "Ren", "взять stone_flat_1", "same-interaction"
    )
    second = app.handle_act(
        "discord-a", "Ren", "взять stone_flat_1", "same-interaction"
    )

    assert second == first
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 1


def test_unknown_act_input_returns_help_without_event(tmp_path):
    db, app = make_app(tmp_path)

    text = app.handle_act(
        "discord-a", "Ren", "станцевать на крыше", "interaction-unknown"
    )

    assert "Пока понимаю" in text
    assert "идти village_square" in text
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 0


def test_limit_message_bounds_long_discord_output():
    text = limit_message("x" * 3000, limit=1900)
    assert len(text) <= 1900
    assert text.endswith("…")
