from pathlib import Path

from samseberpg.db import GameDatabase


def make_db(tmp_path: Path) -> GameDatabase:
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty()
    return db


def test_player_resources_bootstrap_with_no_money_or_lodging(tmp_path: Path) -> None:
    db = make_db(tmp_path)
    assert hasattr(db, "fetch_player_resources")
    assert db.fetch_player_resources("player_1") == {
        "coins": 0,
        "lodging_secured": False,
    }


def test_day_service_module_exists() -> None:
    import importlib.util
    assert importlib.util.find_spec("samseberpg.day") is not None


def test_day_service_does_not_teleport_autonomous_npcs_at_tick_eight(tmp_path: Path) -> None:
    from samseberpg.day import DayService

    db = make_db(tmp_path)
    day = DayService()
    with db.connect() as conn:
        day.advance(conn, 8)
        mira = conn.execute(
            "SELECT location_id FROM entities WHERE entity_id='mira_craftswoman'"
        ).fetchone()[0]
        kaspar = conn.execute(
            "SELECT location_id FROM entities WHERE entity_id='kaspar_forager'"
        ).fetchone()[0]
        oren = conn.execute(
            "SELECT location_id FROM entities WHERE entity_id='oren_innkeeper'"
        ).fetchone()[0]

    assert mira == "workshop_yard"
    assert kaspar == "river_edge"
    assert oren == "village_square"
    assert db.get_world_time() == 8


def test_day_advance_invokes_callback_for_each_intermediate_tick(tmp_path: Path) -> None:
    from samseberpg.day import DayService

    db = make_db(tmp_path)
    seen: list[int] = []
    with db.connect() as conn:
        DayService().advance(conn, 3, on_tick=lambda _conn, tick: seen.append(tick))

    assert seen == [1, 2, 3]
    assert db.get_world_time() == 3


def test_look_is_free_but_meaningful_actions_advance_time(tmp_path: Path) -> None:
    from samseberpg.domain import ActionType, CanonicalAction
    from samseberpg.game import GameService
    db = make_db(tmp_path)
    game = GameService(db, seed=1)
    assert game.execute(CanonicalAction("player_1", ActionType.LOOK)).success
    assert db.get_world_time() == 0
    assert game.execute(CanonicalAction("player_1", ActionType.TAKE, item_id="stone_flat_1")).success
    assert db.get_world_time() == 1
    assert game.execute(CanonicalAction("player_1", ActionType.DROP, item_id="stone_flat_1")).success
    assert db.get_world_time() == 2
    assert game.execute(CanonicalAction("player_1", ActionType.MOVE, destination_id="village_square")).success
    assert db.get_world_time() == 3


def test_day_phase_reaches_evening_after_twelve_ticks() -> None:
    from samseberpg.day import DayService
    day = DayService()
    assert day.phase(0) == "утро"
    assert day.phase(4) == "день"
    assert day.phase(8) == "под вечер"
    assert day.phase(12) == "вечер"


def test_bootstrap_upgrades_existing_world_with_new_first_day_state(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "legacy.db")
    db.initialize()
    with db.connect() as conn:
        conn.execute("INSERT INTO player_state(player_id, location_id) VALUES ('player_1','workshop_yard')")
    db.bootstrap_if_empty()
    assert db.fetch_player_resources("player_1") == {"coins": 0, "lodging_secured": False}
    assert db.fetch_entity("driftwood_1") is not None
