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
    assert "бросить stone_flat_1 в tavern_sign" in text
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 0


def test_limit_message_bounds_long_discord_output():
    text = limit_message("x" * 3000, limit=1900)
    assert len(text) <= 1900
    assert text.endswith("…")


def test_discord_app_throw_is_visible_to_second_player_and_retry_safe(tmp_path):
    import json

    db, app = make_app(tmp_path)
    assert "Вы берёте" in app.handle_act(
        "discord-a", "Ren", "взять stone_flat_1", "take-stone"
    )
    assert "переходите" in app.handle_act(
        "discord-a", "Ren", "идти village_square", "move-a-square"
    )

    first = app.handle_act(
        "discord-a",
        "Ren",
        "бросить stone_flat_1 в tavern_sign",
        "throw-sign-same",
    )
    second = app.handle_act(
        "discord-a",
        "Ren",
        "бросить stone_flat_1 в tavern_sign",
        "throw-sign-same",
    )
    assert first == second

    app.handle_act(
        "discord-b", "Other", "идти village_square", "move-b-square"
    )
    other_view = app.handle_look("discord-b", "Other")
    assert "Вывеска таверны" in other_view
    assert "состояние: 80%" in other_view

    with db.connect() as conn:
        state = json.loads(
            conn.execute(
                "SELECT state_json FROM entities WHERE id = 'tavern_sign'"
            ).fetchone()[0]
        )
        throw_events = conn.execute(
            "SELECT COUNT(*) FROM action_events WHERE action_type = 'THROW'"
        ).fetchone()[0]
    assert state["condition"] == 80
    assert throw_events == 1


def test_discord_app_can_give_food_to_present_npc(tmp_path):
    db, app = make_app(tmp_path)
    app.handle_act("discord-a", "Ren", "идти village_square", "move-square")
    app.handle_act("discord-a", "Ren", "взять bread_1", "take-bread")

    response = app.handle_act(
        "discord-a", "Ren", "дать bread_1 npc_oren", "give-bread"
    )

    assert "передаёте Каравай хлеба" in response
    with db.connect() as conn:
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'bread_1'"
        ).fetchone()[0]
    assert owner == "npc_oren"


def test_discord_app_renders_sale_money_and_filled_bottle(tmp_path):
    db, app = make_app(tmp_path)
    app.handle_act("discord-a", "Ren", "идти village_square", "eco-move")

    square = app.handle_look("discord-a", "Ren")
    before = app.handle_me("discord-a", "Ren")
    assert "Пустая бутылка" in square
    assert "цена: 3 монеты" in square
    assert "**Монеты:** 10" in before

    buy = app.handle_act(
        "discord-a",
        "Ren",
        "купить bottle_1 у npc_oren",
        "eco-buy",
    )
    assert "покупаете Пустая бутылка за 3 монеты" in buy
    after_buy = app.handle_me("discord-a", "Ren")
    assert "**Монеты:** 7" in after_buy
    assert "Пустая бутылка" in after_buy

    use = app.handle_act(
        "discord-a",
        "Ren",
        "использовать bottle_1 на village_well",
        "eco-use",
    )
    assert "наполняете Пустая бутылка водой" in use
    after_use = app.handle_me("discord-a", "Ren")
    assert "внутри: water" in after_use

    with db.connect() as conn:
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 23


def test_discord_buy_retry_does_not_double_charge(tmp_path):
    db, app = make_app(tmp_path)
    app.handle_act("discord-a", "Ren", "идти village_square", "retry-move")
    first = app.handle_act(
        "discord-a", "Ren", "купить bottle_1 у npc_oren", "retry-buy"
    )
    second = app.handle_act(
        "discord-a", "Ren", "купить bottle_1 у npc_oren", "retry-buy"
    )
    assert first == second
    with db.connect() as conn:
        player = conn.execute(
            "SELECT actor_id FROM players WHERE discord_user_id = 'discord-a'"
        ).fetchone()[0]
        assert conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?", (player,)
        ).fetchone()[0] == 7
        assert conn.execute(
            "SELECT coins FROM npcs WHERE actor_id = 'npc_oren'"
        ).fetchone()[0] == 23
