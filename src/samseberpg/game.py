from __future__ import annotations

import json
import random
from uuid import uuid4

from .clock import Clock
from .db import DEFAULT_WORLD_ID, GameDatabase
from .domain import (
    ActionResult,
    ActionType,
    CanonicalAction,
    VisibleActor,
    VisibleEntity,
    WorldView,
)
from .progression import ProgressionService
from .world import WorldSynchronizer


class GameService:
    def __init__(self, db: GameDatabase, clock: Clock, seed: int = 0) -> None:
        self.db = db
        self.clock = clock
        self.synchronizer = WorldSynchronizer()
        self.progression = ProgressionService()
        self.rng = random.Random(seed)

    def register_player(self, discord_user_id: str, name: str) -> str:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT actor_id FROM players WHERE discord_user_id = ?",
                (discord_user_id,),
            ).fetchone()
            if row is not None:
                conn.execute("COMMIT")
                return str(row[0])

            player_id = f"player_{uuid4().hex}"
            created_at = _timestamp(self.clock)
            conn.execute(
                "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
                "VALUES (?, ?, 'player', ?, 'workshop_yard', ?)",
                (player_id, DEFAULT_WORLD_ID, name, created_at),
            )
            conn.execute(
                "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
                "VALUES (?, ?, ?, 10)",
                (player_id, discord_user_id, created_at),
            )
            conn.execute("COMMIT")
            return player_id
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def observe(self, player_id: str) -> WorldView:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self.synchronizer.catch_up(conn, DEFAULT_WORLD_ID, self.clock.now())
            player = conn.execute(
                "SELECT actors.location_id, locations.name, locations.description "
                "FROM players "
                "JOIN actors ON actors.id = players.actor_id "
                "JOIN locations ON locations.id = actors.location_id "
                "WHERE players.actor_id = ?",
                (player_id,),
            ).fetchone()
            if player is None:
                raise LookupError(f"player not found: {player_id}")

            location_id = str(player[0])
            actor_rows = conn.execute(
                "SELECT id, name, actor_type FROM actors "
                "WHERE location_id = ? AND id <> ? ORDER BY actor_type, name, id",
                (location_id, player_id),
            ).fetchall()
            entity_rows = conn.execute(
                "SELECT id, name, entity_type, portable FROM entities "
                "WHERE location_id = ? AND owner_actor_id IS NULL ORDER BY name, id",
                (location_id,),
            ).fetchall()
            inventory_rows = conn.execute(
                "SELECT id, name, entity_type, portable FROM entities "
                "WHERE owner_actor_id = ? ORDER BY name, id",
                (player_id,),
            ).fetchall()
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

        return WorldView(
            player_id=player_id,
            location_id=location_id,
            location_name=str(player[1]),
            location_description=str(player[2]),
            visible_actors=tuple(_visible_actor(row) for row in actor_rows),
            visible_entities=tuple(_visible_entity(row) for row in entity_rows),
            inventory=tuple(_visible_entity(row) for row in inventory_rows),
        )

    def execute(self, action: CanonicalAction, external_id: str | None = None) -> ActionResult:
        conn = self.db.connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self.synchronizer.catch_up(conn, DEFAULT_WORLD_ID, self.clock.now())
            if external_id is not None:
                replay_row = conn.execute(
                    "SELECT result_json FROM processed_interactions WHERE external_id = ?",
                    (external_id,),
                ).fetchone()
                if replay_row is not None:
                    stored = json.loads(str(replay_row[0]))
                    conn.execute("COMMIT")
                    return ActionResult(
                        success=bool(stored["success"]),
                        code=str(stored["code"]),
                        summary=str(stored["summary"]),
                        event_id=int(stored["event_id"]),
                        replayed=True,
                    )

            player = conn.execute(
                "SELECT actors.location_id FROM players "
                "JOIN actors ON actors.id = players.actor_id "
                "WHERE players.actor_id = ?",
                (action.actor_id,),
            ).fetchone()

            if player is None:
                result = self._record_result(
                    conn,
                    action,
                    external_id,
                    actor_id=None,
                    location_id=None,
                    success=False,
                    code="PLAYER_NOT_FOUND",
                    summary="Player not found.",
                )
                conn.execute("COMMIT")
                return result

            location_id = str(player[0])
            success, code, summary, event_location, evidence = self._resolve_action(
                conn, action, location_id
            )
            result = self._record_result(
                conn,
                action,
                external_id,
                actor_id=action.actor_id,
                location_id=event_location,
                success=success,
                code=code,
                summary=summary,
                evidence=evidence,
            )
            if action.action_type is ActionType.THROW and result.success:
                self.progression.evaluate_throwing(
                    conn, action.actor_id, _timestamp(self.clock)
                )
            conn.execute("COMMIT")
            return result
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def _resolve_action(
        self, conn, action: CanonicalAction, location_id: str
    ) -> tuple[bool, str, str, str, dict[str, object]]:
        if action.action_type is ActionType.LOOK:
            return True, "OK", "Looked around.", location_id, {}

        if action.action_type is ActionType.MOVE:
            destination_id = action.destination_id
            adjacent = (
                destination_id is not None
                and conn.execute(
                    "SELECT 1 FROM location_edges "
                    "WHERE from_location_id = ? AND to_location_id = ?",
                    (location_id, destination_id),
                ).fetchone()
                is not None
            )
            if not adjacent:
                return False, "INVALID_DESTINATION", "Destination is not adjacent.", location_id, {}
            conn.execute(
                "UPDATE actors SET location_id = ? WHERE id = ?",
                (destination_id, action.actor_id),
            )
            return True, "OK", f"Moved to {destination_id}.", str(destination_id), {}

        if action.action_type is ActionType.TAKE:
            entity = conn.execute(
                "SELECT location_id, owner_actor_id, portable FROM entities WHERE id = ?",
                (action.target_id,),
            ).fetchone()
            if entity is None:
                return False, "TARGET_NOT_FOUND", "Target does not exist.", location_id, {}
            if entity[1] is not None:
                return False, "ALREADY_OWNED", "Target is already owned.", location_id, {}
            if entity[0] != location_id:
                return False, "TARGET_NOT_PRESENT", "Target is not present here.", location_id, {}
            if not bool(entity[2]):
                return False, "NOT_PORTABLE", "Target cannot be carried.", location_id, {}
            conn.execute(
                "UPDATE entities SET location_id = NULL, owner_actor_id = ? WHERE id = ?",
                (action.actor_id, action.target_id),
            )
            return True, "OK", f"Took {action.target_id}.", location_id, {}

        if action.action_type is ActionType.DROP:
            entity = conn.execute(
                "SELECT owner_actor_id FROM entities WHERE id = ?",
                (action.target_id,),
            ).fetchone()
            if entity is None or entity[0] != action.actor_id:
                return False, "ITEM_NOT_OWNED", "Item is not owned by this player.", location_id, {}
            conn.execute(
                "UPDATE entities SET owner_actor_id = NULL, location_id = ? WHERE id = ?",
                (location_id, action.target_id),
            )
            return True, "OK", f"Dropped {action.target_id}.", location_id, {}

        if action.action_type is ActionType.THROW:
            if action.item_id is None:
                return False, "ITEM_REQUIRED", "A projectile item is required.", location_id, {}
            entity = conn.execute(
                "SELECT owner_actor_id, state_json, entity_type FROM entities WHERE id = ?",
                (action.item_id,),
            ).fetchone()
            if entity is None or entity[0] != action.actor_id:
                return False, "ITEM_NOT_OWNED", "Projectile is not owned by this player.", location_id, {}

            state = json.loads(str(entity[1]))
            if "improvised_projectile" not in state.get("tags", []):
                return False, "ITEM_NOT_THROWABLE", "Item cannot be used as a projectile.", location_id, {}

            target = conn.execute(
                "SELECT location_id FROM actors WHERE id = ?",
                (action.target_id,),
            ).fetchone()
            if target is None:
                return False, "TARGET_NOT_FOUND", "Target does not exist.", location_id, {}
            if target[0] != location_id:
                return False, "TARGET_NOT_PRESENT", "Target is not present here.", location_id, {}

            aimed = bool(action.modifiers and action.modifiers.get("aimed") is True)
            if aimed:
                ability = conn.execute(
                    "SELECT 1 FROM abilities WHERE actor_id = ? AND ability_id = 'aimed_throw'",
                    (action.actor_id,),
                ).fetchone()
                if ability is None:
                    return (
                        False,
                        "ACTION_NOT_UNLOCKED",
                        "Aimed Throw has not been unlocked.",
                        location_id,
                        {"aimed": True},
                    )

            accuracy_chance = 0.55 if aimed else 0.45
            accuracy_roll = self.rng.random()
            hit = accuracy_roll < accuracy_chance
            conn.execute(
                "UPDATE entities SET owner_actor_id = NULL, location_id = ? WHERE id = ?",
                (location_id, action.item_id),
            )
            projectile_type = str(state.get("projectile_type", entity[2]))
            outcome = "hit" if hit else "miss"
            return (
                True,
                "OK",
                f"Threw {action.item_id} at {action.target_id}: {outcome}.",
                location_id,
                {
                    "item_id": action.item_id,
                    "projectile_type": projectile_type,
                    "aimed": aimed,
                    "accuracy_chance": accuracy_chance,
                    "hit": hit,
                    "accuracy_roll": accuracy_roll,
                },
            )

        raise ValueError(f"unsupported action type: {action.action_type}")

    def _record_result(
        self,
        conn,
        action: CanonicalAction,
        external_id: str | None,
        *,
        actor_id: str | None,
        location_id: str | None,
        success: bool,
        code: str,
        summary: str,
        evidence: dict[str, object] | None = None,
    ) -> ActionResult:
        evidence_payload = {
            key: value
            for key, value in {
                "destination_id": action.destination_id,
                "item_id": action.item_id,
                "modifiers": action.modifiers,
                "source_text": action.source_text,
            }.items()
            if value is not None
        }
        if evidence:
            evidence_payload.update(evidence)
        cursor = conn.execute(
            "INSERT INTO action_events "
            "(world_id, external_id, occurred_at, actor_id, action_type, target_id, location_id, "
            "success, result_code, summary, evidence_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                DEFAULT_WORLD_ID,
                external_id,
                _timestamp(self.clock),
                actor_id,
                action.action_type.value,
                action.target_id,
                location_id,
                int(success),
                code,
                summary,
                json.dumps(evidence_payload, separators=(",", ":"), sort_keys=True),
            ),
        )
        result = ActionResult(
            success=success,
            code=code,
            summary=summary,
            event_id=int(cursor.lastrowid),
        )
        if external_id is not None:
            processed_at = _timestamp(self.clock)
            conn.execute(
                "INSERT INTO processed_interactions "
                "(external_id, world_id, actor_id, action_event_id, result_json, processed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    external_id,
                    DEFAULT_WORLD_ID,
                    actor_id,
                    result.event_id,
                    json.dumps(
                        {
                            "success": result.success,
                            "code": result.code,
                            "summary": result.summary,
                            "event_id": result.event_id,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                    processed_at,
                ),
            )
        return result


def _visible_actor(row) -> VisibleActor:
    return VisibleActor(actor_id=str(row[0]), name=str(row[1]), actor_type=str(row[2]))


def _visible_entity(row) -> VisibleEntity:
    return VisibleEntity(
        entity_id=str(row[0]),
        name=str(row[1]),
        entity_type=str(row[2]),
        portable=bool(row[3]),
    )


def _timestamp(clock: Clock) -> str:
    return clock.now().isoformat(timespec="milliseconds").replace("+00:00", "Z")
