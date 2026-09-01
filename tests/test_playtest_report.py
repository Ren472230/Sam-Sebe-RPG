from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.game import GameService
from samseberpg.playtest import PlaytestService


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _insert_action(
    db: GameDatabase,
    *,
    player_id: str,
    occurred_at: datetime,
    action_type: str,
    success: bool = True,
    result_code: str = "OK",
    target_id: str | None = None,
    location_id: str = "workshop_yard",
    evidence: dict | None = None,
    summary: str | None = None,
) -> None:
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO action_events "
            "(world_id, external_id, occurred_at, actor_id, action_type, target_id, location_id, success, result_code, summary, evidence_json) "
            "VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                DEFAULT_WORLD_ID,
                _timestamp(occurred_at),
                player_id,
                action_type,
                target_id,
                location_id,
                int(success),
                result_code,
                summary or f"{action_type} {result_code}",
                json.dumps(evidence or {}, separators=(",", ":"), sort_keys=True),
            ),
        )


def _build_completed_session(tmp_path: Path):
    db = GameDatabase(tmp_path / "playtest.sqlite3")
    db.initialize()
    start = datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc)
    clock = FakeClock(start)
    game = GameService(db, clock)
    player_id = game.register_player("playtest-player", "Playtest Player")
    service = PlaytestService(db, clock)

    service.record(
        "session-pass",
        "SESSION_START",
        player_id=player_id,
        summary="Autonomous route started",
        evidence={"world_tick": 0, "location_id": "workshop_yard"},
    )
    clock.advance(timedelta(milliseconds=100))
    service.record(
        "session-pass",
        "GAME_BOOT",
        player_id=player_id,
        summary="Playable frame rendered",
        evidence={"backend_healthy": True, "first_playable_frame": True},
    )
    clock.advance(timedelta(milliseconds=100))
    service.record(
        "session-pass",
        "SCENE_ENTER",
        player_id=player_id,
        summary="Entered tavern",
        evidence={"scene": "tavern"},
    )
    clock.advance(timedelta(milliseconds=100))
    service.record(
        "session-pass",
        "DIALOGUE_OPEN",
        player_id=player_id,
        summary="Opened dialogue with Oren",
        evidence={"npc_id": "npc_oren"},
    )

    event_time = start + timedelta(seconds=1)
    _insert_action(
        db,
        player_id=player_id,
        occurred_at=event_time,
        action_type="QUEST_ACCEPT",
        location_id="tavern_interior",
    )
    for index in range(1, 5):
        event_time += timedelta(milliseconds=100)
        _insert_action(
            db,
            player_id=player_id,
            occurred_at=event_time,
            action_type="TAKE",
            target_id=f"firewood_{index}",
        )
    event_time += timedelta(milliseconds=100)
    _insert_action(
        db,
        player_id=player_id,
        occurred_at=event_time,
        action_type="QUEST_TURN_IN",
        success=False,
        result_code="INSUFFICIENT_FIREWOOD",
        location_id="tavern_interior",
        summary="Oren still needs 1 more firewood.",
    )
    event_time += timedelta(milliseconds=100)
    _insert_action(
        db,
        player_id=player_id,
        occurred_at=event_time,
        action_type="TAKE",
        target_id="firewood_5",
    )
    event_time += timedelta(milliseconds=100)
    _insert_action(
        db,
        player_id=player_id,
        occurred_at=event_time,
        action_type="QUEST_TURN_IN",
        location_id="tavern_interior",
        summary="Delivered five firewood to Oren.",
    )
    event_time += timedelta(milliseconds=100)
    _insert_action(
        db,
        player_id=player_id,
        occurred_at=event_time,
        action_type="WAIT",
        location_id="tavern_interior",
        evidence={"modifiers": {"ticks": 5}},
        summary="Waited 5 simulation tick(s).",
    )

    with db.connect() as conn:
        accepted_at = _timestamp(start + timedelta(seconds=1))
        completed_at = _timestamp(start + timedelta(seconds=2))
        conn.execute(
            "INSERT INTO quests (id, world_id, player_actor_id, quest_type, giver_actor_id, status, accepted_at, completed_at) "
            "VALUES (?, ?, ?, 'bring_5_firewood', 'npc_oren', 'completed', ?, ?)",
            (f"bring_5_firewood:{player_id}", DEFAULT_WORLD_ID, player_id, accepted_at, completed_at),
        )
        conn.execute("UPDATE players SET coins = 15 WHERE actor_id = ?", (player_id,))
        conn.execute(
            "INSERT INTO relations (source_actor_id, target_actor_id, familiarity, trust, affinity, fear, conflict, romance, updated_at) "
            "VALUES ('npc_oren', ?, 5, 10, 0, 0, 0, 0, ?)",
            (player_id, completed_at),
        )
        conn.execute("UPDATE world_runtime SET tick = 5 WHERE world_id = ?", (DEFAULT_WORLD_ID,))
        conn.execute(
            "INSERT INTO world_events (world_id, tick, actor_id, event_type, target_id, location_id, data_json, summary) "
            "VALUES (?, 1, 'npc_mira', 'NPC_REQUESTED_RESOURCE', 'driftwood_1', 'workshop_yard', '{}', 'Mira requested useful wood.')",
            (DEFAULT_WORLD_ID,),
        )
        conn.execute(
            "INSERT INTO world_events (world_id, tick, actor_id, event_type, target_id, location_id, data_json, summary) "
            "VALUES (?, 2, 'npc_kaspar', 'NPC_MOVED', NULL, 'village_square', '{}', 'Kaspar moved toward the request.')",
            (DEFAULT_WORLD_ID,),
        )

    clock.set(start + timedelta(seconds=3))
    service.record(
        "session-pass",
        "PAGE_RELOAD",
        player_id=player_id,
        summary="Page reloaded after quest completion",
        evidence={"world_tick": 5, "location_id": "tavern_interior"},
    )
    return service, clock, player_id


def test_report_reconstructs_pass_without_requiring_session_end(tmp_path: Path) -> None:
    service, _, _ = _build_completed_session(tmp_path)

    report = service.report("session-pass", commit="abc123")

    assert report["commit"] == "abc123"
    assert report["result"] == "PASS"
    assert report["verdict"] == "SAFE FOR HUMAN EXPERIENCE TEST"
    assert report["player_route"] == {
        "entered_tavern": True,
        "talked_to_oren": True,
        "quest_accepted": True,
        "collected_5_firewood": True,
        "early_turn_in_rejected": True,
        "quest_completed": True,
        "reward_received": True,
        "persistence_after_reload": True,
    }
    assert report["living_world"]["steps_advanced"] == 5
    assert report["living_world"]["meaningful_events_observed"] == 2
    assert report["errors"] == {
        "expected_gameplay_failures": 1,
        "unexpected_backend_failures": 0,
        "client_errors": 0,
        "console_errors": 0,
        "crashes": 0,
    }
    assert any(item["source"] == "world" for item in report["timeline"])
    assert "Expected gameplay failures: 1" in report["markdown"]
    assert "SAFE FOR HUMAN EXPERIENCE TEST" in report["markdown"]


def test_console_error_turns_reconstructed_session_into_fail(tmp_path: Path) -> None:
    service, clock, player_id = _build_completed_session(tmp_path)
    clock.advance(timedelta(milliseconds=100))
    service.record(
        "session-pass",
        "CONSOLE_ERROR",
        player_id=player_id,
        success=False,
        summary="WebGL context lost",
    )

    report = service.report("session-pass")

    assert report["result"] == "FAIL"
    assert report["verdict"] == "NOT SAFE FOR HUMAN EXPERIENCE TEST"
    assert report["errors"]["console_errors"] == 1
    assert report["boot"]["no_fatal_console_errors"] is False
