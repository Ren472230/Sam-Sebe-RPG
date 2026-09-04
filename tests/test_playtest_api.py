from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from samseberpg.api import create_app
from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService


def make_client(db_path: Path) -> TestClient:
    db = GameDatabase(db_path)
    db.initialize()
    clock = FakeClock(datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc))
    game = GameService(db, clock, living_world=LivingWorldService())
    quest = QuestService(db, clock)
    dialogue = DialogueService(db, quest, provider=None)
    return TestClient(create_app(game, quest, dialogue))


def test_playtest_event_and_report_endpoints_use_session_contract(tmp_path: Path) -> None:
    client = make_client(tmp_path / "world.sqlite3")
    session = client.post(
        "/api/session",
        json={"external_id": "playtest-api", "name": "Playtest API"},
    ).json()
    player_id = session["player_id"]
    state = client.get(f"/api/state/{player_id}").json()

    started = client.post(
        "/api/playtest/event",
        json={
            "session_id": "api-session",
            "player_id": player_id,
            "event_type": "SESSION_START",
            "success": True,
            "summary": "started",
            "evidence": {
                "world_tick": state["world_pulse"]["tick"],
                "location_id": state["location"]["id"],
            },
        },
    )
    assert started.status_code == 200
    assert isinstance(started.json()["event_id"], int)

    boot = client.post(
        "/api/playtest/event",
        json={
            "session_id": "api-session",
            "player_id": player_id,
            "event_type": "GAME_BOOT",
            "success": True,
            "summary": "booted",
            "evidence": {
                "backend_healthy": True,
                "first_playable_frame": True,
            },
        },
    )
    assert boot.status_code == 200

    report = client.get("/api/playtest/report/api-session?commit=test-sha")
    assert report.status_code == 200
    payload = report.json()
    assert payload["commit"] == "test-sha"
    assert payload["session"] == "api-session"
    assert payload["result"] == "FAIL"
    assert payload["boot"]["backend_started"] is True
    assert payload["boot"]["first_playable_frame"] is True
    assert payload["verdict"] == "NOT SAFE FOR HUMAN EXPERIENCE TEST"


def test_playtest_event_endpoint_rejects_unknown_client_event(tmp_path: Path) -> None:
    client = make_client(tmp_path / "world.sqlite3")

    response = client.post(
        "/api/playtest/event",
        json={
            "session_id": "bad-session",
            "event_type": "SOMETHING_RANDOM",
            "success": True,
            "summary": "should fail",
        },
    )

    assert response.status_code == 400
    assert "unsupported playtest event" in response.json()["detail"]
