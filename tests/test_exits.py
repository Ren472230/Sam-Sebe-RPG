from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    return GameService(db, FakeClock(now))


def test_world_view_exposes_only_adjacent_exits(tmp_path):
    game = make_game(tmp_path)
    player = game.register_player("discord-exits", "Explorer")

    yard = game.observe(player)
    assert yard.exits == ("village_square",)

    assert game.execute(
        CanonicalAction(player, ActionType.MOVE, destination_id="village_square")
    ).success
    square = game.observe(player)
    assert set(square.exits) == {"workshop_yard", "river_edge"}


def test_look_renders_canonical_exit_ids(tmp_path):
    game = make_game(tmp_path)
    app = DiscordGameApplication(game)
    text = app.handle_look("discord-exit-view", "Explorer")
    assert "**Выходы:**" in text
    assert "`village_square`" in text
