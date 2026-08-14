from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.presentation import render_action_result, render_me


def main() -> None:
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-progression-") as temp_dir:
        path = Path(temp_dir) / "game.db"
        db = GameDatabase(path)
        db.initialize()
        db.bootstrap_if_empty(now)
        game = GameService(db, FakeClock(now))
        player = game.register_player("demo-progression", "Ren")

        assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
        assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
        first = game.execute(
            CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
            external_id="progress-throw-1",
        )
        assert first.success and "unlocks" not in first.data
        assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_flat_1")).success
        second = game.execute(
            CanonicalAction(player, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
            external_id="progress-throw-2",
        )
        assert second.success and "unlocks" not in second.data
        print("[behavior] Two successful throws with one projectile: no unlock")

        assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="workshop_yard")).success
        assert game.execute(CanonicalAction(player, ActionType.TAKE, target_id="stone_round_1")).success
        assert game.execute(CanonicalAction(player, ActionType.MOVE, destination_id="village_square")).success
        trigger = game.execute(
            CanonicalAction(player, ActionType.THROW, item_id="stone_round_1", target_id="tavern_sign"),
            external_id="progress-throw-3",
        )
        assert trigger.success
        assert trigger.data["damage"] == 20
        assert [unlock["code"] for unlock in trigger.data["unlocks"]] == [
            "THROWING_HABIT_1",
            "STEADY_HAND",
        ]
        print("[emergent unlock] Third qualifying throw with a second projectile:")
        print(render_action_result(trigger))

        view = game.observe(player)
        me_text = render_me(view)
        assert "Рука помнит дугу" in me_text
        assert "Твёрдая рука" in me_text
        print("[player state] /me now exposes the earned achievement and skill")

        reopened = GameDatabase(path)
        reopened.initialize()
        restarted = GameService(reopened, FakeClock(now))
        assert restarted.execute(
            CanonicalAction(player, ActionType.TAKE, target_id="stone_round_1"),
            external_id="progress-retake",
        ).success
        boosted = restarted.execute(
            CanonicalAction(player, ActionType.THROW, item_id="stone_round_1", target_id="tavern_sign"),
            external_id="progress-boosted",
        )
        assert boosted.success
        assert boosted.data["base_damage"] == 20
        assert boosted.data["ability_bonus"] == 5
        assert boosted.data["damage"] == 25
        assert boosted.data["condition_before"] == 40
        assert boosted.data["condition_after"] == 15
        print("[mechanic] After restart, STEADY_HAND changes future THROW: 20 + 5 = 25 damage")
        print("\nEmergent Progression demo: PASS")


if __name__ == "__main__":
    main()
