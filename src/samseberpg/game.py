from __future__ import annotations

import json
import sqlite3

from .day import DayService
from .db import GameDatabase
from .domain import ActionResult, ActionType, CanonicalAction
from .game_base import GameService as _BaseGameService
from .living_world import LivingWorldService
from .progression import ProgressionService
from .social import SocialService


class _LivingDayService(DayService):
    def __init__(self, living_world: LivingWorldService):
        self.living_world = living_world

    def advance(self, conn: sqlite3.Connection, ticks: int, *, on_tick=None) -> int:
        return super().advance(
            conn,
            ticks,
            on_tick=on_tick or self.living_world.tick,
        )


class _StateAwareSocialService(SocialService):
    def __init__(self, db: GameDatabase):
        self.db = db

    def talk_summary(self, npc_id, trust, topic=None, *, state=None):
        if state is None:
            entity = self.db.fetch_entity(npc_id)
            state = entity["state"] if entity is not None else {}
        return super().talk_summary(npc_id, trust, topic, state=state)


class GameService(_BaseGameService):
    """Authoritative game service with deterministic Living World ticks attached."""

    def __init__(self, db: GameDatabase, seed: int = 0):
        super().__init__(db, seed=seed)
        self.living_world = LivingWorldService()
        self.day = _LivingDayService(self.living_world)
        self.social = _StateAwareSocialService(db)

    def execute(self, action: CanonicalAction) -> ActionResult:
        """Resolve one action and finalize evidence at the action completion tick.

        The inherited handlers still own immediate authoritative mutations. This wrapper owns
        the cross-cutting contract added by Audit Fix Pack A: start/resolve timing, local
        Living World observability, and completion-time progression timestamps.
        """
        with self.db.connect() as conn:
            start_tick = self._world_time(conn)
            action_event_before = self._last_action_event_id(conn)
            world_event_before = self._last_world_event_id(conn)
            achievements_before = self._player_ids(conn, "achievements", "achievement_id", action.actor_id)
            abilities_before = self._player_ids(conn, "abilities", "ability_id", action.actor_id)

            player = conn.execute(
                "SELECT player_id, location_id FROM player_state WHERE player_id = ?",
                (action.actor_id,),
            ).fetchone()
            if player is None:
                result = self._record(
                    conn, action, None, False, "PLAYER_NOT_FOUND", "Игрок не найден."
                )
            else:
                location_id = player["location_id"]
                handlers = {
                    ActionType.LOOK: self._look,
                    ActionType.MOVE: self._move,
                    ActionType.TAKE: self._take,
                    ActionType.DROP: self._drop,
                    ActionType.THROW: self._throw,
                    ActionType.TALK: self._talk,
                    ActionType.GIVE: self._give,
                    ActionType.FEED: self._feed,
                    ActionType.WAIT: self._wait,
                }
                handler = handlers.get(action.action_type)
                if handler is None:
                    result = self._record(
                        conn,
                        action,
                        location_id,
                        False,
                        "ACTION_NOT_IMPLEMENTED",
                        "Это действие пока недоступно.",
                    )
                else:
                    result = handler(conn, action, location_id)

            resolved_tick = self._world_time(conn)
            duration = max(0, resolved_tick - start_tick)
            event_id = self._last_action_event_id(conn)
            if event_id > action_event_before:
                conn.execute(
                    """
                    UPDATE action_events
                    SET world_time = ?, started_at_tick = ?, resolved_at_tick = ?, duration_ticks = ?
                    WHERE event_id = ?
                    """,
                    (resolved_tick, start_tick, resolved_tick, duration, event_id),
                )

            self._retime_new_progression(
                conn,
                action.actor_id,
                resolved_tick,
                achievements_before,
                abilities_before,
            )

            player_after = conn.execute(
                "SELECT location_id FROM player_state WHERE player_id = ?",
                (action.actor_id,),
            ).fetchone()
            location_after = player_after["location_id"] if player_after is not None else None
            observed = self._observable_world_events_since(
                conn, world_event_before, location_after
            )
            data = dict(result.data)
            data["observed_world_events"] = observed
            return ActionResult(
                success=result.success,
                code=result.code,
                summary=result.summary,
                data=data,
            )

    def _last_action_event_id(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COALESCE(MAX(event_id), 0) AS value FROM action_events").fetchone()
        return int(row["value"])

    def _last_world_event_id(self, conn: sqlite3.Connection) -> int:
        row = conn.execute("SELECT COALESCE(MAX(event_id), 0) AS value FROM world_events").fetchone()
        return int(row["value"])

    def _player_ids(
        self,
        conn: sqlite3.Connection,
        table: str,
        id_column: str,
        player_id: str,
    ) -> set[str]:
        rows = conn.execute(
            f"SELECT {id_column} FROM {table} WHERE player_id = ?",
            (player_id,),
        ).fetchall()
        return {str(row[id_column]) for row in rows}

    def _retime_new_progression(
        self,
        conn: sqlite3.Connection,
        player_id: str,
        resolved_tick: int,
        achievements_before: set[str],
        abilities_before: set[str],
    ) -> None:
        achievements_after = self._player_ids(
            conn, "achievements", "achievement_id", player_id
        )
        abilities_after = self._player_ids(conn, "abilities", "ability_id", player_id)
        for achievement_id in achievements_after - achievements_before:
            conn.execute(
                """
                UPDATE achievements SET unlocked_at = ?
                WHERE player_id = ? AND achievement_id = ?
                """,
                (resolved_tick, player_id, achievement_id),
            )
        for ability_id in abilities_after - abilities_before:
            conn.execute(
                """
                UPDATE abilities SET unlocked_at = ?
                WHERE player_id = ? AND ability_id = ?
                """,
                (resolved_tick, player_id, ability_id),
            )

    def _observable_world_events_since(
        self,
        conn: sqlite3.Connection,
        after_event_id: int,
        location_id: str | None,
    ) -> list[dict[str, object]]:
        if location_id is None:
            return []
        rows = conn.execute(
            """
            SELECT event_id, world_time, actor_id, event_type, target_id,
                   location_id, data_json, summary
            FROM world_events
            WHERE event_id > ? AND location_id = ?
            ORDER BY event_id
            """,
            (after_event_id, location_id),
        ).fetchall()
        events: list[dict[str, object]] = []
        for row in rows:
            event = dict(row)
            event["data"] = json.loads(event.pop("data_json"))
            events.append(event)
        return events

    def _throw(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        if not action.item_id:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_REQUIRED",
                "Нужно указать предмет.",
            )
        if not action.target_id:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "TARGET_REQUIRED",
                "Нужно указать цель.",
            )
        if not self._owns_item(conn, action.actor_id, action.item_id):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_OWNED",
                "Этого предмета нет в инвентаре.",
            )

        item = conn.execute(
            "SELECT tags_json FROM entities WHERE entity_id = ?", (action.item_id,)
        ).fetchone()
        tags = json.loads(item["tags_json"]) if item else []
        if "improvised_projectile" not in tags:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_THROWABLE",
                "Этот предмет не подходит для броска в пилоте.",
            )

        target = conn.execute(
            """
            SELECT entity_id, entity_type, state_json
            FROM entities
            WHERE entity_id = ? AND location_id = ?
            """,
            (action.target_id, location_id),
        ).fetchone()
        if target is None:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "TARGET_NOT_PRESENT",
                "Этой цели здесь нет.",
            )

        aimed = bool(action.modifiers.get("aimed", False))
        accuracy_bonus = self._aimed_accuracy_bonus(conn, action.actor_id, aimed)
        if accuracy_bonus is None:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ACTION_NOT_UNLOCKED",
                "Точный бросок ещё не освоен.",
            )

        roll = self._next_roll(conn)
        chance = 0.45 + accuracy_bonus
        hit = roll < chance
        projectile_types = [tag for tag in tags if tag != "improvised_projectile"]
        projectile_type = projectile_types[0] if projectile_types else "unknown"

        self._remove_from_inventory(conn, action.actor_id, action.item_id)
        conn.execute(
            "UPDATE entities SET location_id = ? WHERE entity_id = ?",
            (location_id, action.item_id),
        )

        social_effects: dict[str, float] = {}
        animal_effects: dict[str, object] = {}
        precision_task_completed = False

        if hit and action.target_id == "target_sign":
            self.social.change_trust(conn, "oren_innkeeper", action.actor_id, -1)
            social_effects["oren_trust_delta"] = -1

        if hit and target["entity_type"] == "npc":
            self.social.change_trust(conn, action.target_id, action.actor_id, -2)
            social_effects["target_trust_delta"] = -2
            state = json.loads(target["state_json"])
            state["hit_by_player_count"] = int(state.get("hit_by_player_count", 0)) + 1
            conn.execute(
                "UPDATE entities SET state_json = ? WHERE entity_id = ?",
                (json.dumps(state, ensure_ascii=False), action.target_id),
            )

        if hit and target["entity_type"] == "animal":
            state = json.loads(target["state_json"])
            state["fear"] = int(state.get("fear", 0)) + 2
            state["trust"] = int(state.get("trust", 0)) - 1
            if location_id == "village_square":
                fled_to = "river_edge"
            elif location_id == "river_edge":
                fled_to = "village_square"
            else:
                fled_to = "village_square"
            conn.execute(
                "UPDATE entities SET state_json = ?, location_id = ? WHERE entity_id = ?",
                (json.dumps(state, ensure_ascii=False), fled_to, action.target_id),
            )
            animal_effects = {
                "fear_delta": 2,
                "trust_delta": -1,
                "fled_to": fled_to,
            }

        if hit and aimed and action.target_id == "target_barrel":
            barrel_state = json.loads(target["state_json"])
            mira_present = self._entity_present(
                conn, "mira_craftswoman", "npc", "workshop_yard"
            )
            if not bool(barrel_state.get("precision_fixed", False)) and mira_present:
                barrel_state["precision_fixed"] = True
                conn.execute(
                    "UPDATE entities SET state_json = ? WHERE entity_id = 'target_barrel'",
                    (json.dumps(barrel_state, ensure_ascii=False),),
                )
                self.social.change_trust(conn, "mira_craftswoman", action.actor_id, 1)
                social_effects["mira_trust_delta"] = 1
                precision_task_completed = True

        summary = (
            f"{action.item_id} попадает в {action.target_id}."
            if hit
            else f"{action.item_id} пролетает мимо {action.target_id}."
        )
        if hit and target["entity_type"] == "npc":
            summary += " Человек резко отстраняется и явно запоминает этот поступок."
        if hit and target["entity_type"] == "animal":
            summary += " Испуганное животное срывается с места и улетает прочь."
        if precision_task_completed:
            summary += (
                " Точный удар ставит перекошенную деталь старой бочки на место; "
                "Мира замечает удачную работу."
            )

        result = self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            summary,
            behavior_tags=["throwing", "improvised_projectile"],
            evidence={
                "hit": hit,
                "accuracy_roll": roll,
                "base_accuracy": chance,
                "projectile_type": projectile_type,
                "target_id": action.target_id,
                "location_id": location_id,
                "aimed": aimed,
                "social_effects": social_effects,
                "animal_effects": animal_effects,
                "precision_task_completed": precision_task_completed,
            },
            data={
                "hit": hit,
                "accuracy_roll": roll,
                "accuracy": chance,
                "social_effects": social_effects,
                "animal_effects": animal_effects,
                "precision_task_completed": precision_task_completed,
            },
        )
        ProgressionService(self.db).evaluate(action.actor_id, conn)
        self.day.advance(conn, 1)
        return result
