from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def ids(items):
    return {item.id for item in items}


def main() -> None:
    morning = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    evening = datetime(2026, 8, 14, 20, 0, tzinfo=timezone.utc)

    with TemporaryDirectory(prefix="sam-sebe-rpg-") as temp_dir:
        db_path = Path(temp_dir) / "game.db"
        db = GameDatabase(db_path)
        db.initialize()
        db.bootstrap_if_empty(morning)
        clock = FakeClock(morning)
        game = GameService(db, clock)

        ren = game.register_player("demo-ren", "Ren")
        other = game.register_player("demo-player", "TestPlayer")
        assert "stone_flat_1" in ids(game.observe(ren).entities)
        assert "stone_flat_1" in ids(game.observe(other).entities)
        print("[shared] Оба игрока видят stone_flat_1 во дворе мастерской")

        result = game.execute(
            CanonicalAction(ren, ActionType.TAKE, target_id="stone_flat_1"),
            external_id="demo-take-1",
        )
        assert result.success
        assert "stone_flat_1" in ids(game.observe(ren).inventory)
        assert "stone_flat_1" not in ids(game.observe(other).entities)
        print("[consequence] Ren забрал камень; второй игрок больше не видит его на земле")

        reopened = GameDatabase(db_path)
        reopened.initialize()
        game_after_restart = GameService(reopened, clock)
        assert "stone_flat_1" in ids(game_after_restart.observe(ren).inventory)
        print("[persistence] После переоткрытия БД камень всё ещё принадлежит Ren")

        clock.set(evening)
        game_after_restart.observe(other)
        with reopened.connect() as conn:
            mira = conn.execute(
                "SELECT location_id FROM actors WHERE id = 'npc_mira'"
            ).fetchone()[0]
        assert mira == "village_square"
        print("[offline-time] К 20:00 Мира перешла на деревенскую площадь")

        replay = game_after_restart.execute(
            CanonicalAction(ren, ActionType.TAKE, target_id="stone_flat_1"),
            external_id="demo-take-1",
        )
        assert replay.success and replay.replayed
        print("[idempotency] Повтор interaction ID безопасно вернул исходный результат")
        print("\nShared World Kernel demo: PASS")


if __name__ == "__main__":
    main()
