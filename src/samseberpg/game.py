from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from .day import DayService
from .db import GameDatabase
from .domain import ActionResult, ActionType, CanonicalAction, MechanicSpec
from .progression import MechanicValidator, ProgressionService
from .social import SocialService
from .world import LOCATION_GRAPH


class GameService:
    """The only authoritative mutation boundary for the pilot world."""

    def __init__(self, db: GameDatabase, seed: int = 0):
        self.db = db
        self.day = DayService()
        self.social = SocialService()
        with self.db.connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO world_meta(key, value) VALUES ('rng_seed', ?)",
                (str(seed),),
            )
            conn.execute(
                "INSERT OR IGNORE INTO world_meta(key, value) VALUES ('rng_counter', '0')"
            )

    def execute(self, action: CanonicalAction) -> ActionResult:
        with self.db.connect() as conn:
            player = conn.execute(
                "SELECT player_id, location_id FROM player_state WHERE player_id = ?",
                (action.actor_id,),
            ).fetchone()
            if player is None:
                return self._record(
                    conn, action, None, False, "PLAYER_NOT_FOUND", "Игрок не найден."
                )

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
                return self._record(
                    conn,
                    action,
                    location_id,
                    False,
                    "ACTION_NOT_IMPLEMENTED",
                    "Это действие пока недоступно.",
                )
            return handler(conn, action, location_id)

    def _look(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        entities = conn.execute(
            """
            SELECT entity_id, entity_type, name
            FROM entities
            WHERE location_id = ?
            ORDER BY entity_type, entity_id
            """,
            (location_id,),
        ).fetchall()
        data = {
            "location_id": location_id,
            "entities": [dict(row) for row in entities],
            "exits": sorted(LOCATION_GRAPH.get(location_id, set())),
        }
        return self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            "Ты осматриваешься.",
            data=data,
        )

    def _move(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        destination = action.destination_id
        if destination not in LOCATION_GRAPH.get(location_id, set()):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "INVALID_DESTINATION",
                "Отсюда туда нельзя пройти напрямую.",
            )
        conn.execute(
            "UPDATE player_state SET location_id = ? WHERE player_id = ?",
            (destination, action.actor_id),
        )
        result = self._record(
            conn,
            action,
            destination,
            True,
            "OK",
            f"Ты переходишь в {destination}.",
        )
        self.day.advance(conn, 1)
        return result

    def _take(
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
        item = conn.execute(
            "SELECT entity_type, location_id FROM entities WHERE entity_id = ?",
            (action.item_id,),
        ).fetchone()
        if (
            item is None
            or item["entity_type"] != "item"
            or item["location_id"] != location_id
        ):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_PRESENT",
                "Этого предмета здесь нет.",
            )
        conn.execute(
            "INSERT INTO inventory(player_id, item_id) VALUES (?, ?)",
            (action.actor_id, action.item_id),
        )
        conn.execute(
            "UPDATE entities SET location_id = NULL WHERE entity_id = ?",
            (action.item_id,),
        )
        result = self._record(
            conn, action, location_id, True, "OK", f"Ты берёшь {action.item_id}."
        )
        self.day.advance(conn, 1)
        return result

    def _drop(
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
        if not self._owns_item(conn, action.actor_id, action.item_id):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_OWNED",
                "Этого предмета нет в инвентаре.",
            )
        self._remove_from_inventory(conn, action.actor_id, action.item_id)
        conn.execute(
            "UPDATE entities SET location_id = ? WHERE entity_id = ?",
            (location_id, action.item_id),
        )
        result = self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            f"Ты оставляешь {action.item_id}.",
        )
        self.day.advance(conn, 1)
        return result

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
            "SELECT entity_id FROM entities WHERE entity_id = ? AND location_id = ?",
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
        if hit and action.target_id == "target_sign":
            self.social.change_trust(conn, "oren_innkeeper", action.actor_id, -1)
            social_effects["oren_trust_delta"] = -1

        summary = (
            f"{action.item_id} попадает в {action.target_id}."
            if hit
            else f"{action.item_id} пролетает мимо {action.target_id}."
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
            },
            data={
                "hit": hit,
                "accuracy_roll": roll,
                "accuracy": chance,
                "social_effects": social_effects,
            },
        )
        ProgressionService(self.db).evaluate(action.actor_id, conn)
        self.day.advance(conn, 1)
        return result

    def _talk(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        if not action.target_id:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "TARGET_REQUIRED",
                "Нужно указать, с кем поговорить.",
            )
        if not self._entity_present(conn, action.target_id, "npc", location_id):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "NPC_NOT_PRESENT",
                "Этого человека здесь нет.",
            )

        trust = self.social.get_trust(conn, action.target_id, action.actor_id)
        topic = action.modifiers.get("topic")
        evidence: dict[str, Any] = {"trust": trust}

        if action.target_id == "oren_innkeeper" and topic == "lodging":
            summary = (
                "Орен говорит, что место на ночь стоит 3 монеты. "
                "Если кто-то из местных поручится за тебя, он готов обойтись без платы."
            )
            evidence["lodging"] = {"secured": False, "route": "information"}
        elif action.target_id == "oren_innkeeper" and topic == "pay_lodging":
            lodging = self.social.pay_lodging(conn, action.actor_id)
            evidence["lodging"] = lodging
            if lodging["secured"] and lodging["route"] == "coins":
                summary = "Орен принимает 3 монеты и оставляет за тобой место на ночь."
            elif lodging["secured"]:
                summary = "Место на ночь за тобой уже закреплено."
            else:
                summary = "Орен качает головой: на ночлег нужно 3 монеты."
        elif action.target_id == "oren_innkeeper" and topic == "request_lodging":
            lodging = self.social.request_lodging(conn, action.actor_id)
            evidence["lodging"] = lodging
            if lodging["secured"] and lodging["route"] == "trust":
                summary = (
                    "Орен кивает: за тебя поручились местные, место на ночь найдётся."
                )
            elif lodging["secured"]:
                summary = "Место на ночь за тобой уже закреплено."
            else:
                summary = (
                    "Орен пока не готов дать место без платы: тебя здесь ещё почти не знают."
                )
        else:
            summary = self.social.talk_summary(action.target_id, trust, topic)

        result = self._record(
            conn, action, location_id, True, "OK", summary, evidence=evidence
        )
        self.day.advance(conn, 1)
        return result

    def _give(
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
                "Нужно указать, кому отдать предмет.",
            )
        if not self._entity_present(conn, action.target_id, "npc", location_id):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "NPC_NOT_PRESENT",
                "Этого человека здесь нет.",
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
        effect = self.social.apply_gift(
            conn, action.actor_id, action.target_id, action.item_id, tags
        )
        self._remove_from_inventory(conn, action.actor_id, action.item_id)
        conn.execute(
            "UPDATE entities SET location_id = NULL WHERE entity_id = ?",
            (action.item_id,),
        )

        if effect["coins_delta"] or effect["trust_delta"]:
            summary = f"{action.target_id} принимает {action.item_id} с явным интересом."
        else:
            summary = f"{action.target_id} принимает {action.item_id}, но без особого интереса."
        result = self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            summary,
            behavior_tags=["social_gift"],
            evidence={"gift_effect": effect},
            data=effect,
        )
        self.day.advance(conn, 1)
        return result

    def _feed(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        if not action.item_id:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_REQUIRED",
                "Нужно указать еду.",
            )
        if not action.target_id:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "TARGET_REQUIRED",
                "Нужно указать животное.",
            )
        if not self._entity_present(conn, action.target_id, "animal", location_id):
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ANIMAL_NOT_PRESENT",
                "Этого животного здесь нет.",
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
        if "food" not in tags:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "ITEM_NOT_FOOD",
                "Этим животное не покормишь.",
            )

        effect = self.social.feed_animal(
            conn, action.actor_id, action.target_id, action.item_id
        )
        self._remove_from_inventory(conn, action.actor_id, action.item_id)
        conn.execute(
            "UPDATE entities SET location_id = NULL WHERE entity_id = ?",
            (action.item_id,),
        )
        result = self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            f"{action.target_id} осторожно принимает еду.",
            behavior_tags=["animal_care"],
            evidence=effect,
            data=effect,
        )
        self.day.advance(conn, 1)
        return result

    def _wait(
        self, conn: sqlite3.Connection, action: CanonicalAction, location_id: str
    ) -> ActionResult:
        try:
            ticks = int(action.modifiers.get("ticks", 1))
        except (TypeError, ValueError):
            ticks = 0
        if ticks < 1 or ticks > 100:
            return self._record(
                conn,
                action,
                location_id,
                False,
                "INVALID_WAIT",
                "Ожидание должно быть от 1 до 100 тактов.",
            )
        new_time = self.day.advance(conn, ticks)
        return self._record(
            conn,
            action,
            location_id,
            True,
            "OK",
            f"Проходит {ticks} такт(а/ов).",
            data={"world_time": new_time},
        )

    def _aimed_accuracy_bonus(
        self, conn: sqlite3.Connection, player_id: str, aimed: bool
    ) -> float | None:
        if not aimed:
            return 0.0
        unlocked = conn.execute(
            """
            SELECT mechanic_json
            FROM abilities
            WHERE player_id = ? AND ability_id = 'aimed_throw'
            """,
            (player_id,),
        ).fetchone()
        if unlocked is None:
            return None

        mechanic = json.loads(unlocked["mechanic_json"])
        spec = MechanicSpec(
            primitive=mechanic.get("primitive", ""),
            value=mechanic.get("value", 0),
            action=mechanic.get("action"),
            variant=mechanic.get("variant"),
            condition=mechanic.get("condition"),
        )
        valid, reason = MechanicValidator().validate(spec)
        if not valid or spec.action != "THROW" or spec.variant != "aimed":
            raise ValueError(f"Invalid persisted aimed_throw mechanic: {reason}")
        return float(spec.value) / 100.0

    def _owns_item(
        self, conn: sqlite3.Connection, player_id: str, item_id: str
    ) -> bool:
        row = conn.execute(
            "SELECT 1 FROM inventory WHERE player_id = ? AND item_id = ?",
            (player_id, item_id),
        ).fetchone()
        return row is not None

    def _remove_from_inventory(
        self, conn: sqlite3.Connection, player_id: str, item_id: str
    ) -> None:
        conn.execute(
            "DELETE FROM inventory WHERE player_id = ? AND item_id = ?",
            (player_id, item_id),
        )

    def _entity_present(
        self,
        conn: sqlite3.Connection,
        entity_id: str,
        entity_type: str,
        location_id: str,
    ) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM entities
            WHERE entity_id = ? AND entity_type = ? AND location_id = ?
            """,
            (entity_id, entity_type, location_id),
        ).fetchone()
        return row is not None

    def _next_roll(self, conn: sqlite3.Connection) -> float:
        seed_row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'rng_seed'"
        ).fetchone()
        counter_row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'rng_counter'"
        ).fetchone()
        if seed_row is None or counter_row is None:
            raise RuntimeError("RNG state is not initialized")
        seed = seed_row["value"]
        counter = int(counter_row["value"])
        digest = hashlib.sha256(f"{seed}:{counter}".encode("utf-8")).digest()
        roll = int.from_bytes(digest[:8], "big") / 2**64
        conn.execute(
            "UPDATE world_meta SET value = ? WHERE key = 'rng_counter'",
            (str(counter + 1),),
        )
        return roll

    def _world_time(self, conn: sqlite3.Connection) -> int:
        row = conn.execute(
            "SELECT value FROM world_meta WHERE key = 'world_time'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def _record(
        self,
        conn: sqlite3.Connection,
        action: CanonicalAction,
        location_id: str | None,
        success: bool,
        code: str,
        summary: str,
        *,
        behavior_tags: list[str] | None = None,
        evidence: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> ActionResult:
        conn.execute(
            """
            INSERT INTO action_events(
                world_time, actor_id, action_type, target_id, item_id, location_id,
                success, result_code, behavior_tags_json, evidence_json, summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._world_time(conn),
                action.actor_id,
                action.action_type.value,
                action.target_id,
                action.item_id,
                location_id,
                int(success),
                code,
                json.dumps(behavior_tags or []),
                json.dumps(evidence or {}),
                summary,
            ),
        )
        return ActionResult(
            success=success,
            code=code,
            summary=summary,
            data=data or {},
        )
