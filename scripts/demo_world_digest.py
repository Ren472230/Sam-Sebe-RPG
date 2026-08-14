from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def main() -> None:
    start = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-digest-") as temp_dir:
        db = GameDatabase(Path(temp_dir) / "game.db")
        db.initialize()
        db.bootstrap_if_empty(start)
        clock = FakeClock(start)
        game = GameService(db, clock)
        app = DiscordGameApplication(game)

        player_a = game.register_player("digest-demo-a", "Алина")
        game.execute(CanonicalAction(player_a, ActionType.LOOK), external_id="digest-demo-anchor")

        player_b = game.register_player("digest-demo-b", "Борис")
        assert game.execute(CanonicalAction(player_b, ActionType.TAKE, target_id="stone_flat_1")).success
        assert game.execute(CanonicalAction(player_b, ActionType.MOVE, destination_id="village_square")).success
        assert game.execute(
            CanonicalAction(player_b, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
            external_id="digest-demo-throw",
        ).success

        clock.set(datetime(2026, 8, 14, 19, 0, tzinfo=timezone.utc))
        news = app.handle_news("digest-demo-a", "Алина")
        assert "Борис" in news
        assert "Вывеска таверны" in news and "80%" in news
        assert "Мира" in news and "village_square" in news
        assert "Каспар" in news and "village_square" in news
        print(news)
        print("\nWorld Digest demo: PASS")


if __name__ == "__main__":
    main()
