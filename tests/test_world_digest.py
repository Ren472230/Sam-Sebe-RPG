from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.digest import WorldDigestService
from samseberpg.discord_app import DiscordGameApplication
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    clock = FakeClock(now)
    game = GameService(db, clock)
    return db, clock, game


def make_other_player_damage_sign(game):
    player_b = game.register_player("digest-b", "Борис")
    assert game.execute(CanonicalAction(player_b, ActionType.TAKE, target_id="stone_flat_1")).success
    assert game.execute(CanonicalAction(player_b, ActionType.MOVE, destination_id="village_square")).success
    result = game.execute(
        CanonicalAction(player_b, ActionType.THROW, item_id="stone_flat_1", target_id="tavern_sign"),
        external_id="digest-b-throw",
    )
    assert result.success
    return player_b, result


def test_digest_uses_latest_own_event_as_anchor_and_reports_notable_other_action(tmp_path):
    db, _, game = make_game(tmp_path)
    player_a = game.register_player("digest-a", "Алина")
    anchor = game.execute(CanonicalAction(player_a, ActionType.LOOK), external_id="a-last-action")
    _, throw = make_other_player_damage_sign(game)

    digest = WorldDigestService(game).build(player_a)

    assert digest.since_event_id == anchor.event_id
    assert digest.latest_event_id == throw.event_id
    assert [event.action_type for event in digest.events] == ["THROW"]
    assert digest.events[0].actor_name == "Борис"
    assert digest.events[0].summary == throw.summary
    assert all(event.actor_id != player_a for event in digest.events)
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 4


def test_digest_reports_persistent_damage_even_if_damage_is_older_than_player_anchor(tmp_path):
    _, _, game = make_game(tmp_path)
    player_a = game.register_player("digest-damage-a", "Алина")
    make_other_player_damage_sign(game)
    later = game.execute(CanonicalAction(player_a, ActionType.LOOK), external_id="a-after-damage")

    digest = WorldDigestService(game).build(player_a)

    assert digest.since_event_id == later.event_id
    assert digest.events == ()
    sign = next(entity for entity in digest.damaged_entities if entity.id == "tavern_sign")
    assert sign.condition == 80


def test_digest_applies_lazy_catch_up_and_reports_current_npc_status(tmp_path):
    _, clock, game = make_game(tmp_path)
    player_a = game.register_player("digest-time-a", "Алина")
    game.execute(CanonicalAction(player_a, ActionType.LOOK), external_id="a-time-anchor")
    clock.set(datetime(2026, 8, 14, 19, 0, tzinfo=timezone.utc))

    digest = WorldDigestService(game).build(player_a)

    mira = next(npc for npc in digest.npcs if npc.id == "npc_mira")
    kaspar = next(npc for npc in digest.npcs if npc.id == "npc_kaspar")
    assert mira.location_id == "village_square"
    assert "тавер" in mira.activity
    assert kaspar.location_id == "village_square"


def test_handle_news_is_repeatable_and_does_not_append_events(tmp_path):
    db, clock, game = make_game(tmp_path)
    app = DiscordGameApplication(game)
    player_a = game.register_player("news-a", "Алина")
    game.execute(CanonicalAction(player_a, ActionType.LOOK), external_id="news-a-anchor")
    make_other_player_damage_sign(game)
    clock.set(datetime(2026, 8, 14, 19, 0, tzinfo=timezone.utc))

    with db.connect() as conn:
        before = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]
    first = app.handle_news("news-a", "Алина")
    second = app.handle_news("news-a", "Алина")
    with db.connect() as conn:
        after = conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0]

    assert first == second
    assert after == before
    assert "Деревенская сводка" in first
    assert "Борис" in first
    assert "Вывеска таверны" in first and "80%" in first
    assert "Мира" in first and "village_square" in first
    assert "Каспар" in first and "village_square" in first
