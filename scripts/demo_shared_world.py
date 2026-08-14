from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def entity_ids(view) -> set[str]:
    return {entity.entity_id for entity in view.visible_entities}


def inventory_ids(view) -> set[str]:
    return {entity.entity_id for entity in view.inventory}


def main() -> None:
    with TemporaryDirectory(prefix="samseberpg-demo-") as tmp:
        db_path = Path(tmp) / "world.sqlite3"
        clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
        db = GameDatabase(db_path)
        db.initialize()
        game = GameService(db, clock)
        player_a = game.register_player("demo-player-a", "Ari")
        player_b = game.register_player("demo-player-b", "Bela")

        initial_a = game.observe(player_a)
        initial_b = game.observe(player_b)
        assert "stone_flat_1" in entity_ids(initial_a)
        assert "stone_flat_1" in entity_ids(initial_b)
        print("1. Both players see stone_flat_1 in workshop_yard")

        take = game.execute(
            CanonicalAction(actor_id=player_a, action_type=ActionType.TAKE, target_id="stone_flat_1"),
            external_id="demo-take-1",
        )
        assert take.success
        after_b = game.observe(player_b)
        assert "stone_flat_1" not in entity_ids(after_b)
        print("2. Player A takes it; Player B immediately stops seeing it")

        reopened_db = GameDatabase(db_path)
        reopened_db.initialize()
        reopened = GameService(reopened_db, clock)
        after_restart = reopened.observe(player_a)
        assert "stone_flat_1" in inventory_ids(after_restart)
        print("3. Database reopened; Player A still owns stone_flat_1")

        clock.advance(timedelta(hours=12))
        reopened.observe(player_b)
        with reopened_db.connect() as conn:
            mira = conn.execute(
                "SELECT actors.location_id, npcs.current_activity FROM actors "
                "JOIN npcs ON npcs.actor_id = actors.id WHERE actors.id = 'npc_mira'"
            ).fetchone()
        assert tuple(mira) == ("village_square", "running evening errands")
        print("4. FakeClock advances to 20:00; lazy catch-up moves Mira to village_square")
        print("Shared World Kernel demo: PASS")


if __name__ == "__main__":
    main()
