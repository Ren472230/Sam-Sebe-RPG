from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def act(app, user_id, name, text, interaction_id):
    out = app.handle_act(user_id, name, text, interaction_id)
    print(f"\n> {name}: {text}\n{out}")
    return out


def main() -> None:
    start = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-vertical-") as temp_dir:
        path = Path(temp_dir) / "game.db"
        db = GameDatabase(path)
        db.initialize()
        db.bootstrap_if_empty(start)
        clock = FakeClock(start)
        game = GameService(db, clock)
        app = DiscordGameApplication(game)

        observer = game.register_player("vertical-observer", "Алина")
        game.execute(CanonicalAction(observer, ActionType.LOOK), external_id="observer-anchor")

        act(app, "vertical-ren", "Ren", "сказать npc_mira привет", "v-talk-mira")
        act(app, "vertical-ren", "Ren", "взять stone_flat_1", "v-take-flat")
        act(app, "vertical-ren", "Ren", "идти village_square", "v-move-square")
        act(app, "vertical-ren", "Ren", "взять bread_1", "v-take-bread")
        act(app, "vertical-ren", "Ren", "дать bread_1 npc_oren", "v-give-bread")
        warm_talk = act(app, "vertical-ren", "Ren", "сказать npc_oren как дела", "v-talk-warm")
        assert "смягча" in warm_talk.casefold()

        act(app, "vertical-ren", "Ren", "бросить stone_flat_1 в tavern_sign", "v-throw-1")
        act(app, "vertical-ren", "Ren", "взять stone_flat_1", "v-retake-flat")
        act(app, "vertical-ren", "Ren", "бросить stone_flat_1 в tavern_sign", "v-throw-2")
        act(app, "vertical-ren", "Ren", "идти workshop_yard", "v-back-yard")
        act(app, "vertical-ren", "Ren", "взять stone_round_1", "v-take-round")
        act(app, "vertical-ren", "Ren", "идти village_square", "v-return-square")
        third = act(app, "vertical-ren", "Ren", "бросить stone_round_1 в tavern_sign", "v-throw-3")
        assert "Рука помнит дугу" in third and "Твёрдая рука" in third

        act(app, "vertical-ren", "Ren", "взять stone_round_1", "v-retake-round")
        fourth = act(app, "vertical-ren", "Ren", "бросить stone_round_1 в tavern_sign", "v-throw-4")
        assert "15%" in fourth

        guarded = act(app, "vertical-ren", "Ren", "сказать npc_oren поговорим", "v-talk-guarded")
        assert "насторож" in guarded.casefold() or "шум" in guarded.casefold()

        act(app, "vertical-ren", "Ren", "купить bottle_1 у npc_oren", "v-buy-bottle")
        act(app, "vertical-ren", "Ren", "использовать bottle_1 на village_well", "v-fill-bottle")
        me = app.handle_me("vertical-ren", "Ren")
        assert "Рука помнит дугу" in me
        assert "Твёрдая рука" in me
        assert "water" in me
        assert "**Монеты:** 7" in me

        clock.set(datetime(2026, 8, 14, 19, 0, tzinfo=timezone.utc))
        news = app.handle_news("vertical-observer", "Алина")
        print(f"\n> Алина: /news\n{news}")
        assert "Ren" in news
        assert "Вывеска таверны" in news and "15%" in news
        assert "Мира" in news and "Каспар" in news

        reopened = GameDatabase(path)
        reopened.initialize()
        restarted = GameService(reopened, FakeClock(clock.now()))
        player = restarted.register_player("vertical-ren", "Ren")
        view = restarted.observe(player)
        bottle = next(item for item in view.inventory if item.id == "bottle_1")
        assert bottle.state["filled_with"] == "water"
        assert view.achievement_codes == ("THROWING_HABIT_1",)
        assert view.ability_codes == ("STEADY_HAND",)

        print("\n=== FOUNDER VERTICAL SLICE: PASS ===")


if __name__ == "__main__":
    main()
