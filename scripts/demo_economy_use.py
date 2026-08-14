from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def main() -> None:
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-economy-") as temp_dir:
        path = Path(temp_dir) / "game.db"
        db = GameDatabase(path)
        db.initialize()
        db.bootstrap_if_empty(now)
        game = GameService(db, FakeClock(now))
        player = game.register_player("demo-economy", "Ren")

        assert game.observe(player).coins == 10
        assert game.execute(
            CanonicalAction(player, ActionType.MOVE, destination_id="village_square"),
            external_id="economy-move",
        ).success
        print("[money] Player starts with 10 coins; Oren starts with 20")

        free_take = game.execute(
            CanonicalAction(player, ActionType.TAKE, target_id="bottle_1"),
            external_id="economy-free-take",
        )
        assert not free_take.success and free_take.code == "FOR_SALE_ONLY"
        print("[sale guard] TAKE cannot bypass the bottle offer")

        buy_action = CanonicalAction(
            player,
            ActionType.BUY,
            item_id="bottle_1",
            target_id="npc_oren",
        )
        buy = game.execute(buy_action, external_id="economy-buy")
        replay = game.execute(buy_action, external_id="economy-buy")
        assert buy.success and replay.success and replay.replayed
        with db.connect() as conn:
            oren_coins = conn.execute(
                "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
            ).fetchone()[0]
        assert game.observe(player).coins == 7
        assert oren_coins == 23
        print("[buy] Player 10 -> 7 coins; Oren 20 -> 23; retry charged once")

        fill = game.execute(
            CanonicalAction(
                player,
                ActionType.USE,
                item_id="bottle_1",
                target_id="village_well",
            ),
            external_id="economy-fill",
        )
        assert fill.success
        bottle = next(
            entity for entity in game.observe(player).inventory if entity.id == "bottle_1"
        )
        assert bottle.state["filled_with"] == "water"
        print("[use] Bottle filled with water at the village well")

        reopened = GameDatabase(path)
        reopened.initialize()
        restarted = GameService(reopened, FakeClock(now))
        view = restarted.observe(player)
        bottle = next(entity for entity in view.inventory if entity.id == "bottle_1")
        with reopened.connect() as conn:
            persisted_oren = conn.execute(
                "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
            ).fetchone()[0]
        assert view.coins == 7
        assert persisted_oren == 23
        assert bottle.state["filled_with"] == "water"
        print("[persistence] Restart preserves 7 coins, Oren 23, and water-filled bottle")
        print("\nMinimal Economy + USE demo: PASS")


if __name__ == "__main__":
    main()
