from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from samseberpg.db import GameDatabase
from samseberpg.server import build_app


QUEST_OFFER = "offer_quest:bring_5_firewood"
EXPECTED_COINS = 5
EXPECTED_TRUST = 10


class FailingProvider:
    def generate(self, context):
        raise RuntimeError("LLM intentionally unavailable")


class SmokeFailure(RuntimeError):
    def __init__(self, step: str, expected, actual) -> None:
        super().__init__(f"{step}: expected {expected!r}, got {actual!r}")
        self.step = step
        self.expected = expected
        self.actual = actual


def require(step: str, condition: bool, *, expected, actual) -> None:
    if not condition:
        raise SmokeFailure(step, expected, actual)


def pass_step(step: str) -> None:
    print(f"[PASS] {step}")


def payload(response, step: str) -> dict:
    require(step, response.status_code == 200, expected="HTTP 200", actual=f"HTTP {response.status_code}: {response.text}")
    value = response.json()
    require(step, isinstance(value, dict), expected="JSON object", actual=value)
    return value


def world(state: dict) -> dict:
    legacy = state.get("world")
    if isinstance(legacy, dict):
        for key in ("location_id", "visible_actors", "visible_entities", "inventory"):
            require("state contract", key in legacy, expected=f"world.{key}", actual=legacy)
        require("state contract", legacy["location_id"] == state["location"]["id"], expected=state["location"]["id"], actual=legacy["location_id"])
        return legacy
    return {
        "location_id": state["location"]["id"],
        "visible_actors": state["visible_actors"],
        "visible_entities": state["visible_entities"],
        "inventory": state["inventory"],
    }


def trust(state: dict) -> int:
    if "oren_trust" in state:
        return int(state["oren_trust"])
    relation = state.get("oren_relation")
    if isinstance(relation, dict) and "trust" in relation:
        return int(relation["trust"])
    relations = state.get("relations")
    if isinstance(relations, dict):
        oren = relations.get("npc_oren")
        if isinstance(oren, dict) and "trust" in oren:
            return int(oren["trust"])
    raise SmokeFailure("state contract", "Oren trust/relation", state)


def state(client: TestClient, player_id: str) -> dict:
    value = payload(client.get(f"/api/state/{player_id}"), "state")
    require("state contract", value.get("player_id") == player_id, expected=player_id, actual=value.get("player_id"))
    location = value.get("location")
    require("state contract", isinstance(location, dict), expected="location object", actual=location)
    for key in ("id", "name", "description"):
        require("state contract", key in location, expected=f"location.{key}", actual=location)
    for key in ("visible_actors", "visible_entities", "inventory"):
        require("state contract", isinstance(value.get(key), list), expected=f"{key} list", actual=value.get(key))
    require("state contract", isinstance(value.get("quest"), dict), expected="quest object", actual=value)
    require("state contract", "coins" in value, expected="coins", actual=value)
    require("state contract", isinstance(value.get("oren_relation"), dict) and "trust" in value["oren_relation"], expected="oren_relation.trust", actual=value.get("oren_relation"))
    world(value)
    trust(value)
    return value


def session(client: TestClient, *, name: str = "Player") -> str:
    value = payload(
        client.post("/api/session", json={"external_id": "local-player", "name": name}),
        "session",
    )
    player_id = value.get("player_id")
    require("session", isinstance(player_id, str) and bool(player_id), expected="stable player_id", actual=player_id)
    return player_id


def action(
    client: TestClient,
    player_id: str,
    *,
    action_type: str,
    external_id: str,
    target_id: str | None = None,
    destination_id: str | None = None,
) -> dict:
    return payload(
        client.post(
            "/api/action",
            json={
                "player_id": player_id,
                "action_type": action_type,
                "target_id": target_id,
                "destination_id": destination_id,
                "external_id": external_id,
            },
        ),
        f"action {action_type}",
    )


def move(client: TestClient, player_id: str, destination_id: str, step: str) -> None:
    value = action(
        client,
        player_id,
        action_type="MOVE",
        destination_id=destination_id,
        external_id=f"smoke-move-{step}",
    )
    require(step, value.get("success") is True, expected="successful MOVE", actual=value)


def memory_count(db_path: Path, player_id: str) -> int:
    db = GameDatabase(db_path)
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM npc_memories WHERE npc_actor_id='npc_oren' AND subject_actor_id=?",
                (player_id,),
            ).fetchone()[0]
        )


def successful_turn_ins(db_path: Path, player_id: str) -> int:
    db = GameDatabase(db_path)
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM action_events WHERE actor_id=? AND action_type='QUEST_TURN_IN' AND success=1",
                (player_id,),
            ).fetchone()[0]
        )


def run_smoke(db_path: Path) -> None:
    client = TestClient(build_app(db_path, provider=FailingProvider()))

    health = payload(client.get("/api/health"), "health")
    require("health", health == {"ok": True}, expected={"ok": True}, actual=health)

    player_id = session(client)
    same_player = session(client, name="Reloaded Player")
    require("session", same_player == player_id, expected=player_id, actual=same_player)
    pass_step("session")

    initial = state(client, player_id)
    initial_coins = int(initial["coins"])
    initial_trust = trust(initial)
    initial_memories = memory_count(db_path, player_id)

    move(client, player_id, "village_square", "village square")
    move(client, player_id, "tavern_interior", "tavern reachable")
    tavern_state = state(client, player_id)
    oren_ids = {str(actor.get("actor_id", actor.get("id", ""))) for actor in tavern_state["visible_actors"] if isinstance(actor, dict)}
    require("tavern reachable", "npc_oren" in oren_ids, expected="npc_oren visible", actual=sorted(oren_ids))
    pass_step("tavern reachable")

    dialogue = payload(
        client.post("/api/dialogue", json={"player_id": player_id, "text": "Есть работа?"}),
        "quest offer dialogue",
    )
    require("fallback dialogue", dialogue.get("used_fallback") is True, expected=True, actual=dialogue)
    require("quest offer dialogue", dialogue.get("proposal") == QUEST_OFFER, expected=QUEST_OFFER, actual=dialogue.get("proposal"))

    accepted = payload(
        client.post("/api/quest/accept", json={"player_id": player_id, "external_id": "smoke-accept"}),
        "quest accepted",
    )
    require("quest accepted", accepted.get("success") is True, expected=True, actual=accepted)
    require("quest accepted", accepted.get("state", {}).get("status") == "active", expected="active", actual=accepted)
    pass_step("quest accepted")

    move(client, player_id, "village_square", "leave tavern")
    move(client, player_id, "workshop_yard", "workshop reachable")
    for index in range(1, 6):
        taken = action(
            client,
            player_id,
            action_type="TAKE",
            target_id=f"firewood_{index}",
            external_id=f"smoke-take-{index}",
        )
        require(f"take firewood_{index}", taken.get("success") is True, expected=True, actual=taken)
        current = state(client, player_id)
        require(
            f"firewood count after {index}",
            current["quest"].get("owned_firewood") == index,
            expected=index,
            actual=current["quest"].get("owned_firewood"),
        )
        if index == 4:
            move(client, player_id, "village_square", "early return square")
            move(client, player_id, "tavern_interior", "early return tavern")
            early = payload(
                client.post("/api/quest/turn-in", json={"player_id": player_id, "external_id": "smoke-early-turn-in"}),
                "early turn-in",
            )
            require("early turn-in", early.get("success") is False, expected=False, actual=early)
            require("early turn-in", early.get("code") == "INSUFFICIENT_FIREWOOD", expected="INSUFFICIENT_FIREWOOD", actual=early.get("code"))
            move(client, player_id, "village_square", "resume square")
            move(client, player_id, "workshop_yard", "resume workshop")
    pass_step("5 firewood collected")

    move(client, player_id, "village_square", "final square")
    move(client, player_id, "tavern_interior", "final tavern")
    completed = payload(
        client.post("/api/quest/turn-in", json={"player_id": player_id, "external_id": "smoke-final-turn-in"}),
        "quest completed",
    )
    require("quest completed", completed.get("success") is True, expected=True, actual=completed)
    require("quest completed", completed.get("state", {}).get("status") == "completed", expected="completed", actual=completed)
    pass_step("quest completed")

    completed_state = state(client, player_id)
    require("reward exactly once", int(completed_state["coins"]) == initial_coins + EXPECTED_COINS, expected=initial_coins + EXPECTED_COINS, actual=completed_state["coins"])
    require("relation persisted", trust(completed_state) == initial_trust + EXPECTED_TRUST, expected=initial_trust + EXPECTED_TRUST, actual=trust(completed_state))
    require("memory persisted", memory_count(db_path, player_id) == initial_memories + 1, expected=initial_memories + 1, actual=memory_count(db_path, player_id))
    require("reward exactly once", successful_turn_ins(db_path, player_id) == 1, expected=1, actual=successful_turn_ins(db_path, player_id))

    duplicate = payload(
        client.post("/api/quest/turn-in", json={"player_id": player_id, "external_id": "smoke-duplicate-turn-in"}),
        "duplicate turn-in",
    )
    require("reward exactly once", duplicate.get("code") == "ALREADY_COMPLETED", expected="ALREADY_COMPLETED", actual=duplicate)
    after_duplicate = state(client, player_id)
    require("reward exactly once", int(after_duplicate["coins"]) == int(completed_state["coins"]), expected=completed_state["coins"], actual=after_duplicate["coins"])
    require("reward exactly once", successful_turn_ins(db_path, player_id) == 1, expected=1, actual=successful_turn_ins(db_path, player_id))
    pass_step("reward exactly once")
    pass_step("relation persisted")
    pass_step("memory persisted")

    restarted = TestClient(build_app(db_path, provider=FailingProvider()))
    restored_player = session(restarted)
    require("restart persistence", restored_player == player_id, expected=player_id, actual=restored_player)
    restored = state(restarted, player_id)
    require("restart persistence", restored["quest"].get("status") == "completed", expected="completed", actual=restored["quest"])
    require("restart persistence", int(restored["coins"]) == int(completed_state["coins"]), expected=completed_state["coins"], actual=restored["coins"])
    require("restart persistence", trust(restored) == trust(completed_state), expected=trust(completed_state), actual=trust(restored))
    require("restart persistence", memory_count(db_path, player_id) == initial_memories + 1, expected=initial_memories + 1, actual=memory_count(db_path, player_id))
    pass_step("restart persistence")

    fallback = payload(
        restarted.post("/api/dialogue", json={"player_id": player_id, "text": "Ты меня помнишь?"}),
        "fallback dialogue",
    )
    require("fallback dialogue", fallback.get("used_fallback") is True, expected=True, actual=fallback)
    require("fallback dialogue", "пом" in str(fallback.get("text", "")).lower(), expected="post-quest memory acknowledgement", actual=fallback.get("text"))
    pass_step("fallback dialogue")


def main() -> int:
    try:
        with TemporaryDirectory(prefix="sam-sebe-rpg-smoke-") as temp_dir:
            run_smoke(Path(temp_dir) / "world.sqlite3")
    except SmokeFailure as exc:
        print(f"[FAIL] {exc.step}: expected {exc.expected!r}; actual {exc.actual!r}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[FAIL] unexpected error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("[PASS] vertical slice backend smoke complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
