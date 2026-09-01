from __future__ import annotations

import json
from datetime import timezone
from typing import Any


ALLOWED_CLIENT_EVENTS = {
    "SESSION_START",
    "GAME_BOOT",
    "SCENE_ENTER",
    "DIALOGUE_OPEN",
    "PAGE_RELOAD",
    "CLIENT_ERROR",
    "CONSOLE_ERROR",
    "UNHANDLED_REJECTION",
    "SESSION_END",
}
EXPECTED_GAMEPLAY_FAILURES = {("QUEST_TURN_IN", "INSUFFICIENT_FIREWOOD")}


class PlaytestService:
    def __init__(self, db: Any, clock: Any) -> None:
        self.db = db
        self.clock = clock
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self.db.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS playtest_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    player_id TEXT,
                    occurred_at TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    success INTEGER NOT NULL CHECK (success IN (0, 1)),
                    summary TEXT NOT NULL,
                    evidence_json TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_playtest_events_session_time
                    ON playtest_events(session_id, occurred_at, id);
                CREATE INDEX IF NOT EXISTS idx_playtest_events_player_time
                    ON playtest_events(player_id, occurred_at, id);
                """
            )

    def record(
        self,
        session_id: str,
        event_type: str,
        *,
        player_id: str | None = None,
        success: bool = True,
        summary: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> int:
        session_id = session_id.strip()
        event_type = event_type.strip().upper()
        if not session_id:
            raise ValueError("session_id is required")
        if event_type not in ALLOWED_CLIENT_EVENTS:
            raise ValueError(f"unsupported playtest event: {event_type}")
        occurred_at = _timestamp(self.clock.now())
        payload = json.dumps(evidence or {}, separators=(",", ":"), sort_keys=True)
        with self.db.connect() as conn:
            cursor = conn.execute(
                "INSERT INTO playtest_events (session_id, player_id, occurred_at, event_type, success, summary, evidence_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, player_id, occurred_at, event_type, int(success), summary, payload),
            )
            return int(cursor.lastrowid)

    def report(self, session_id: str, *, commit: str | None = None) -> dict[str, Any]:
        with self.db.connect() as conn:
            client_rows = conn.execute(
                "SELECT id, session_id, player_id, occurred_at, event_type, success, summary, evidence_json "
                "FROM playtest_events WHERE session_id = ? ORDER BY id",
                (session_id,),
            ).fetchall()
            if not client_rows:
                raise LookupError(f"playtest session not found: {session_id}")

            client_events = [_client_event(row) for row in client_rows]
            session_start = next(
                (event for event in client_events if event["event_type"] == "SESSION_START"),
                client_events[0],
            )
            player_id = next(
                (str(event["player_id"]) for event in client_events if event["player_id"]),
                None,
            )
            if player_id is None:
                raise LookupError(f"playtest session has no player: {session_id}")

            start_at = str(session_start["occurred_at"])
            next_start = conn.execute(
                "SELECT occurred_at FROM playtest_events "
                "WHERE event_type = 'SESSION_START' AND player_id = ? AND session_id <> ? AND occurred_at > ? "
                "ORDER BY occurred_at, id LIMIT 1",
                (player_id, session_id, start_at),
            ).fetchone()
            end_at = None if next_start is None else str(next_start[0])

            action_sql = (
                "SELECT id, occurred_at, action_type, target_id, location_id, success, result_code, summary, evidence_json "
                "FROM action_events WHERE actor_id = ? AND occurred_at >= ?"
            )
            params: list[Any] = [player_id, start_at]
            if end_at is not None:
                action_sql += " AND occurred_at < ?"
                params.append(end_at)
            action_sql += " ORDER BY occurred_at, id"
            action_events = [_action_event(row) for row in conn.execute(action_sql, params).fetchall()]

            start_tick = _int_value(session_start["evidence"].get("world_tick"), 0)
            steps_advanced = sum(
                _wait_ticks(event)
                for event in action_events
                if event["success"] and event["action_type"] == "WAIT"
            )
            end_tick = start_tick + steps_advanced
            world_events = []
            if end_tick > start_tick:
                world_rows = conn.execute(
                    "SELECT id, tick, actor_id, event_type, target_id, location_id, summary, data_json "
                    "FROM world_events WHERE tick > ? AND tick <= ? ORDER BY tick, id",
                    (start_tick, end_tick),
                ).fetchall()
                world_events = [_world_event(row) for row in world_rows]

            player = conn.execute(
                "SELECT coins FROM players WHERE actor_id = ?", (player_id,)
            ).fetchone()
            relation = conn.execute(
                "SELECT trust FROM relations WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?",
                (player_id,),
            ).fetchone()
            quest = conn.execute(
                "SELECT status FROM quests WHERE player_actor_id = ? AND quest_type = 'bring_5_firewood'",
                (player_id,),
            ).fetchone()

        coins = 0 if player is None else int(player[0])
        oren_trust = 0 if relation is None else int(relation[0])
        quest_status = "available" if quest is None else str(quest[0])

        expected_failures = [
            event
            for event in action_events
            if not event["success"]
            and (event["action_type"], event["result_code"]) in EXPECTED_GAMEPLAY_FAILURES
        ]
        unexpected_failures = [
            event
            for event in action_events
            if not event["success"]
            and (event["action_type"], event["result_code"]) not in EXPECTED_GAMEPLAY_FAILURES
        ]
        client_errors = [
            event
            for event in client_events
            if event["event_type"] in {"CLIENT_ERROR", "UNHANDLED_REJECTION"}
        ]
        console_errors = [
            event for event in client_events if event["event_type"] == "CONSOLE_ERROR"
        ]
        crashes = [
            event
            for event in client_events
            if event["event_type"] == "GAME_BOOT" and not event["success"]
        ]

        boot_event = next(
            (
                event
                for event in client_events
                if event["event_type"] == "GAME_BOOT" and event["success"]
            ),
            None,
        )
        firewood_taken = {
            str(event["target_id"])
            for event in action_events
            if event["action_type"] == "TAKE"
            and event["success"]
            and str(event["target_id"] or "").startswith("firewood_")
        }
        route = {
            "entered_tavern": any(
                event["event_type"] == "SCENE_ENTER"
                and event["evidence"].get("scene") in {"tavern", "tavern_interior"}
                for event in client_events
            ),
            "talked_to_oren": any(
                event["event_type"] == "DIALOGUE_OPEN"
                and event["evidence"].get("npc_id") == "npc_oren"
                for event in client_events
            ),
            "quest_accepted": any(
                event["action_type"] == "QUEST_ACCEPT" and event["success"]
                for event in action_events
            ),
            "collected_5_firewood": len(firewood_taken) >= 5,
            "early_turn_in_rejected": any(
                event["action_type"] == "QUEST_TURN_IN"
                and not event["success"]
                and event["result_code"] == "INSUFFICIENT_FIREWOOD"
                for event in action_events
            ),
            "quest_completed": any(
                event["action_type"] == "QUEST_TURN_IN" and event["success"]
                for event in action_events
            )
            and quest_status == "completed",
            "reward_received": coins >= 15 and oren_trust >= 10,
            "persistence_after_reload": any(
                event["event_type"] == "PAGE_RELOAD" for event in client_events
            )
            and quest_status == "completed",
        }
        boot = {
            "backend_started": bool(
                boot_event and boot_event["evidence"].get("backend_healthy") is True
            ),
            "frontend_started": boot_event is not None,
            "first_playable_frame": bool(
                boot_event
                and boot_event["evidence"].get("first_playable_frame") is True
            ),
            "no_fatal_console_errors": not client_errors
            and not console_errors
            and not crashes,
        }
        living = {
            "steps_advanced": steps_advanced,
            "meaningful_events_observed": len(world_events),
            "advanced": steps_advanced > 0,
            "meaningful_events": len(world_events) > 0,
        }
        errors = {
            "expected_gameplay_failures": len(expected_failures),
            "unexpected_backend_failures": len(unexpected_failures),
            "client_errors": len(client_errors),
            "console_errors": len(console_errors),
            "crashes": len(crashes),
        }

        checks = [
            _check("backend_started", "backend started", boot["backend_started"]),
            _check("frontend_started", "frontend started", boot["frontend_started"]),
            _check(
                "first_playable_frame",
                "first playable frame rendered",
                boot["first_playable_frame"],
            ),
            _check(
                "no_fatal_console_errors",
                "no fatal console errors",
                boot["no_fatal_console_errors"],
            ),
            _check("entered_tavern", "entered tavern", route["entered_tavern"]),
            _check("talked_to_oren", "talked to Oren", route["talked_to_oren"]),
            _check("quest_accepted", "quest accepted", route["quest_accepted"]),
            _check(
                "collected_5_firewood",
                "collected 5/5 firewood",
                route["collected_5_firewood"],
            ),
            _check(
                "early_turn_in_rejected",
                "early turn-in rejected correctly",
                route["early_turn_in_rejected"],
            ),
            _check("quest_completed", "quest completed", route["quest_completed"]),
            _check("reward_received", "reward received", route["reward_received"]),
            _check(
                "persistence_after_reload",
                "persistence after reload",
                route["persistence_after_reload"],
            ),
            _check(
                "living_world_advanced",
                "Living World advanced",
                living["advanced"],
            ),
            _check(
                "meaningful_world_events",
                "meaningful world events observed",
                living["meaningful_events"],
            ),
        ]
        clean_errors = all(
            errors[key] == 0
            for key in (
                "unexpected_backend_failures",
                "client_errors",
                "console_errors",
                "crashes",
            )
        )
        passed = all(item["passed"] for item in checks) and clean_errors
        result = "PASS" if passed else "FAIL"
        verdict = (
            "SAFE FOR HUMAN EXPERIENCE TEST"
            if passed
            else "NOT SAFE FOR HUMAN EXPERIENCE TEST"
        )
        timeline = _timeline(client_events, action_events, world_events, start_tick)

        report: dict[str, Any] = {
            "commit": commit or "unknown",
            "session": session_id,
            "player_id": player_id,
            "result": result,
            "boot": boot,
            "player_route": route,
            "living_world": living,
            "errors": errors,
            "checks": checks,
            "timeline": timeline,
            "verdict": verdict,
        }
        report["markdown"] = _render_markdown(report)
        return report


def _client_event(row: Any) -> dict[str, Any]:
    return {
        "source": "client",
        "id": int(row[0]),
        "session_id": str(row[1]),
        "player_id": None if row[2] is None else str(row[2]),
        "occurred_at": str(row[3]),
        "event_type": str(row[4]),
        "success": bool(row[5]),
        "summary": str(row[6]),
        "evidence": _json_object(row[7]),
    }


def _action_event(row: Any) -> dict[str, Any]:
    return {
        "source": "action",
        "id": int(row[0]),
        "occurred_at": str(row[1]),
        "action_type": str(row[2]),
        "target_id": None if row[3] is None else str(row[3]),
        "location_id": None if row[4] is None else str(row[4]),
        "success": bool(row[5]),
        "result_code": str(row[6]),
        "summary": str(row[7]),
        "evidence": _json_object(row[8]),
    }


def _world_event(row: Any) -> dict[str, Any]:
    return {
        "source": "world",
        "id": int(row[0]),
        "tick": int(row[1]),
        "actor_id": str(row[2]),
        "event_type": str(row[3]),
        "target_id": None if row[4] is None else str(row[4]),
        "location_id": None if row[5] is None else str(row[5]),
        "summary": str(row[6]),
        "evidence": _json_object(row[7]),
    }


def _timeline(
    client_events: list[dict[str, Any]],
    action_events: list[dict[str, Any]],
    world_events: list[dict[str, Any]],
    start_tick: int,
) -> list[dict[str, Any]]:
    items: list[tuple[str, int, dict[str, Any]]] = []
    for event in client_events:
        items.append((str(event["occurred_at"]), 0, event))
    wait_windows: list[tuple[int, int, str]] = []
    tick = start_tick
    for event in action_events:
        items.append((str(event["occurred_at"]), 1, event))
        if event["success"] and event["action_type"] == "WAIT":
            ticks = _wait_ticks(event)
            wait_windows.append((tick + 1, tick + ticks, str(event["occurred_at"])))
            tick += ticks
    for event in world_events:
        approximate = next(
            (
                stamp
                for first, last, stamp in wait_windows
                if first <= event["tick"] <= last
            ),
            "9999",
        )
        world_copy = dict(event)
        world_copy["occurred_at"] = None if approximate == "9999" else approximate
        items.append((approximate, 2, world_copy))
    items.sort(key=lambda value: (value[0], value[1], int(value[2]["id"])))
    return [item[2] for item in items]


def _wait_ticks(event: dict[str, Any]) -> int:
    modifiers = event["evidence"].get("modifiers")
    if not isinstance(modifiers, dict):
        return 1
    return _int_value(modifiers.get("ticks"), 1)


def _json_object(value: Any) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _int_value(value: Any, default: int) -> int:
    return value if type(value) is int else default


def _check(key: str, label: str, passed: bool) -> dict[str, Any]:
    return {"key": key, "label": label, "passed": bool(passed)}


def _render_markdown(report: dict[str, Any]) -> str:
    by_key = {item["key"]: item for item in report["checks"]}

    def line(key: str) -> str:
        item = by_key[key]
        return f"{'✓' if item['passed'] else '✗'} {item['label']}"

    living = report["living_world"]
    errors = report["errors"]
    timeline_lines = []
    for event in report["timeline"]:
        stamp = event.get("occurred_at") or f"tick {event.get('tick', '?')}"
        kind = event.get("event_type") or event.get("action_type") or "EVENT"
        code = f" [{event['result_code']}]" if event.get("result_code") else ""
        timeline_lines.append(
            f"- {stamp} · {event['source']} · {kind}{code} · {event.get('summary', '')}"
        )

    return "\n".join(
        [
            "# AUTONOMOUS PLAYTEST",
            "",
            f"Commit: {report['commit']}",
            f"Session: {report['session']}",
            f"Result: {report['result']}",
            "",
            "## BOOT",
            line("backend_started"),
            line("frontend_started"),
            line("first_playable_frame"),
            line("no_fatal_console_errors"),
            "",
            "## PLAYER ROUTE",
            line("entered_tavern"),
            line("talked_to_oren"),
            line("quest_accepted"),
            line("collected_5_firewood"),
            line("early_turn_in_rejected"),
            line("quest_completed"),
            line("reward_received"),
            line("persistence_after_reload"),
            "",
            "## LIVING WORLD",
            f"{'✓' if living['advanced'] else '✗'} advanced {living['steps_advanced']} simulation step(s)",
            f"{'✓' if living['meaningful_events'] else '✗'} meaningful world events observed: {living['meaningful_events_observed']}",
            "",
            "## ERRORS",
            f"Expected gameplay failures: {errors['expected_gameplay_failures']}",
            f"Unexpected backend failures: {errors['unexpected_backend_failures']}",
            f"Client errors: {errors['client_errors']}",
            f"Console errors: {errors['console_errors']}",
            f"Crashes: {errors['crashes']}",
            "",
            "## VERDICT",
            str(report["verdict"]),
            "",
            "## TIMELINE",
            *timeline_lines,
            "",
        ]
    )


def _timestamp(value: Any) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
