from __future__ import annotations

import json
from uuid import NAMESPACE_URL, uuid5

from .clock import Clock
from .db import START_LOCATION_ID, WORLD_ID, GameDatabase, to_utc_text
from .domain import ActionResult, ActionType, CanonicalAction, VisibleActor, VisibleEntity, WorldView
from .world import WorldSynchronizer


class GameService:
    def __init__(self, db: GameDatabase, clock: Clock):
        self.db = db
        self.clock = clock
        self.synchronizer = WorldSynchronizer()

    def register_player(self, discord_user_id: str, name: str) -> str:
        if not discord_user_id.strip():
            raise ValueError("discord_user_id must not be empty")
        if not name.strip():
            raise ValueError("name must not be empty")

        now = to_utc_text(self.clock.now())
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                existing = conn.execute(
                    "SELECT actor_id FROM players WHERE discord_user_id = ?",
                    (discord_user_id,),
                ).fetchone()
                if existing:
                    conn.commit()
                    return existing["actor_id"]

                actor_id = f"player_{uuid5(NAMESPACE_URL, 'sam-sebe-rpg:' + discord_user_id).hex[:16]}"
                conn.execute(
                    "INSERT INTO actors(id, world_id, actor_type, name, location_id, created_at) VALUES (?, ?, 'player', ?, ?, ?)",
                    (actor_id, WORLD_ID, name.strip(), START_LOCATION_ID, now),
                )
                conn.execute(
                    "INSERT INTO players(actor_id, discord_user_id, joined_at, coins) VALUES (?, ?, ?, 10)",
                    (actor_id, discord_user_id, now),
                )
                conn.commit()
                return actor_id
            except Exception:
                conn.rollback()
                raise

    def execute(self, action: CanonicalAction, external_id: str | None = None) -> ActionResult:
        now_text = to_utc_text(self.clock.now())
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if external_id is not None:
                    replay = conn.execute(
                        "SELECT result_json FROM processed_interactions WHERE external_id = ?",
                        (external_id,),
                    ).fetchone()
                    if replay is not None:
                        payload = json.loads(replay["result_json"])
                        conn.commit()
                        return ActionResult(
                            success=bool(payload["success"]),
                            code=payload["code"],
                            summary=payload["summary"],
                            event_id=payload["event_id"],
                            data=payload.get("data", {}),
                            replayed=True,
                        )

                self.synchronizer.catch_up(conn, WORLD_ID, self.clock.now())

                actor = conn.execute(
                    "SELECT id, world_id, location_id FROM actors WHERE id = ? AND actor_type = 'player'",
                    (action.actor_id,),
                ).fetchone()
                if actor is None:
                    result = ActionResult(False, "PLAYER_NOT_FOUND", "Игрок не найден.")
                    event_id = self._append_event(conn, action, result, external_id, now_text, None)
                    final = ActionResult(False, result.code, result.summary, event_id=event_id)
                    self._store_interaction(conn, external_id, action.actor_id, final, now_text)
                    conn.commit()
                    return final

                if action.action_type == ActionType.LOOK:
                    result = ActionResult(
                        True,
                        "OK",
                        "Вы осматриваетесь.",
                        data={"location_id": actor["location_id"]},
                    )
                elif action.action_type == ActionType.MOVE:
                    result = self._move(conn, action, actor["location_id"])
                elif action.action_type == ActionType.TAKE:
                    result = self._take(conn, action, actor["location_id"])
                elif action.action_type == ActionType.DROP:
                    result = self._drop(conn, action, actor["location_id"])
                elif action.action_type == ActionType.THROW:
                    result = self._throw(conn, action, actor["location_id"], now_text)
                elif action.action_type == ActionType.GIVE:
                    result = self._give(conn, action, actor["location_id"], now_text)
                elif action.action_type == ActionType.BUY:
                    result = self._buy(conn, action, actor["location_id"])
                elif action.action_type == ActionType.USE:
                    result = self._use(conn, action, actor["location_id"])
                else:
                    raise ValueError(f"unsupported action type: {action.action_type}")

                current_location = conn.execute(
                    "SELECT location_id FROM actors WHERE id = ?",
                    (action.actor_id,),
                ).fetchone()["location_id"]
                event_id = self._append_event(
                    conn, action, result, external_id, now_text, current_location
                )
                final = ActionResult(
                    success=result.success,
                    code=result.code,
                    summary=result.summary,
                    event_id=event_id,
                    data=result.data,
                )
                self._store_interaction(conn, external_id, action.actor_id, final, now_text)
                conn.commit()
                return final
            except Exception:
                conn.rollback()
                raise

    def _move(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        destination = action.destination_id
        if destination is None:
            return ActionResult(False, "INVALID_DESTINATION", "Не указано, куда идти.")
        edge = conn.execute(
            """
            SELECT 1 FROM location_edges
            WHERE world_id = ? AND from_location_id = ? AND to_location_id = ?
            """,
            (WORLD_ID, location_id, destination),
        ).fetchone()
        if edge is None:
            return ActionResult(False, "INVALID_DESTINATION", "Отсюда туда нельзя пройти напрямую.")
        conn.execute(
            "UPDATE actors SET location_id = ? WHERE id = ?",
            (destination, action.actor_id),
        )
        return ActionResult(True, "OK", f"Вы переходите в {destination}.", data={"location_id": destination})

    def _take(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        if action.target_id is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Не указано, что взять.")
        entity = conn.execute(
            "SELECT id, name, location_id, owner_actor_id, portable, state_json FROM entities WHERE id = ?",
            (action.target_id,),
        ).fetchone()
        if entity is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такого объекта нет.")
        if entity["owner_actor_id"] is not None:
            return ActionResult(False, "ALREADY_OWNED", "Этот предмет уже у кого-то.")
        if entity["location_id"] != location_id:
            return ActionResult(False, "TARGET_NOT_PRESENT", "Этого предмета здесь нет.")
        state = json.loads(entity["state_json"])
        if state.get("for_sale_by"):
            return ActionResult(False, "FOR_SALE_ONLY", "Этот предмет выставлен на продажу.")
        if not entity["portable"]:
            return ActionResult(False, "NOT_PORTABLE", "Этот объект нельзя поднять.")
        conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = ? WHERE id = ?",
            (action.actor_id, action.target_id),
        )
        return ActionResult(True, "OK", f"Вы берёте {entity['name']}.", data={"entity_id": action.target_id})

    def _throw(self, conn, action: CanonicalAction, location_id: str, now_text: str) -> ActionResult:
        if action.item_id is None:
            return ActionResult(False, "ITEM_NOT_OWNED", "Не указано, что бросить.")
        item = conn.execute(
            "SELECT id, name, owner_actor_id, state_json FROM entities WHERE id = ?",
            (action.item_id,),
        ).fetchone()
        if item is None or item["owner_actor_id"] != action.actor_id:
            return ActionResult(False, "ITEM_NOT_OWNED", "У вас нет этого предмета.")
        item_state = json.loads(item["state_json"])
        if item_state.get("throwable") is not True:
            return ActionResult(False, "ITEM_NOT_THROWABLE", "Этот предмет нельзя осмысленно бросить в цель.")

        if action.target_id is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Не указана цель броска.")
        target = conn.execute(
            "SELECT id, name, location_id, state_json FROM entities WHERE id = ?",
            (action.target_id,),
        ).fetchone()
        if target is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такой цели нет.")
        if target["location_id"] != location_id:
            return ActionResult(False, "TARGET_NOT_PRESENT", "Этой цели здесь нет.")
        target_state = json.loads(target["state_json"])
        condition = target_state.get("condition")
        if isinstance(condition, bool) or not isinstance(condition, int):
            return ActionResult(False, "TARGET_NOT_DAMAGEABLE", "Эта цель пока не поддерживает повреждения.")

        raw_damage = item_state.get("impact_damage", 20)
        damage = raw_damage if isinstance(raw_damage, int) and not isinstance(raw_damage, bool) and raw_damage > 0 else 20
        before = max(0, min(100, condition))
        after = max(0, before - damage)
        target_state["condition"] = after
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE id = ?",
            (json.dumps(target_state, ensure_ascii=False, sort_keys=True), action.target_id),
        )
        conn.execute(
            "UPDATE entities SET owner_actor_id = NULL, location_id = ? WHERE id = ?",
            (location_id, action.item_id),
        )
        witnesses = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM actors WHERE actor_type = 'npc' AND location_id = ? ORDER BY id",
                (location_id,),
            ).fetchall()
        ]
        relation_deltas: dict[str, dict[str, int]] = {}
        if action.target_id == "tavern_sign" and "npc_oren" in witnesses:
            relation_deltas["npc_oren"] = self._apply_relation_delta(
                conn,
                source_actor_id="npc_oren",
                target_actor_id=action.actor_id,
                now_text=now_text,
                deltas={"trust": -3, "conflict": 4},
            )

        evidence = {
            "item_id": action.item_id,
            "target_id": action.target_id,
            "damage": damage,
            "condition_before": before,
            "condition_after": after,
            "witnesses": witnesses,
            "relation_deltas": relation_deltas,
        }
        return ActionResult(
            True,
            "OK",
            f"{item['name']} ударяет в {target['name']}. Состояние цели: {after}%.",
            data=evidence,
        )

    @staticmethod
    def _apply_relation_delta(
        conn,
        source_actor_id: str,
        target_actor_id: str,
        now_text: str,
        deltas: dict[str, int],
    ) -> dict[str, int]:
        fields = ("familiarity", "trust", "affinity", "fear", "conflict", "romance")
        ranges = {
            "familiarity": (0, 100),
            "trust": (-100, 100),
            "affinity": (-100, 100),
            "fear": (0, 100),
            "conflict": (0, 100),
            "romance": (0, 100),
        }
        if not set(deltas).issubset(fields):
            raise ValueError("unsupported relation field")
        row = conn.execute(
            """
            SELECT familiarity, trust, affinity, fear, conflict, romance
            FROM relations
            WHERE source_actor_id = ? AND target_actor_id = ?
            """,
            (source_actor_id, target_actor_id),
        ).fetchone()
        before = {field: int(row[field]) if row is not None else 0 for field in fields}
        after = before.copy()
        actual: dict[str, int] = {}
        for field, requested in deltas.items():
            low, high = ranges[field]
            value = max(low, min(high, before[field] + int(requested)))
            after[field] = value
            actual[field] = value - before[field]

        conn.execute(
            """
            INSERT INTO relations(
                source_actor_id, target_actor_id, familiarity, trust, affinity,
                fear, conflict, romance, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_actor_id, target_actor_id) DO UPDATE SET
                familiarity = excluded.familiarity,
                trust = excluded.trust,
                affinity = excluded.affinity,
                fear = excluded.fear,
                conflict = excluded.conflict,
                romance = excluded.romance,
                updated_at = excluded.updated_at
            """,
            (
                source_actor_id,
                target_actor_id,
                after["familiarity"],
                after["trust"],
                after["affinity"],
                after["fear"],
                after["conflict"],
                after["romance"],
                now_text,
            ),
        )
        return actual

    def _give(
        self,
        conn,
        action: CanonicalAction,
        location_id: str,
        now_text: str,
    ) -> ActionResult:
        if action.item_id is None:
            return ActionResult(False, "ITEM_NOT_OWNED", "Не указано, что передать.")
        item = conn.execute(
            "SELECT id, name, owner_actor_id, state_json FROM entities WHERE id = ?",
            (action.item_id,),
        ).fetchone()
        if item is None or item["owner_actor_id"] != action.actor_id:
            return ActionResult(False, "ITEM_NOT_OWNED", "У вас нет этого предмета.")

        if action.target_id is None:
            return ActionResult(False, "TARGET_ACTOR_NOT_FOUND", "Не указано, кому передать предмет.")
        target = conn.execute(
            "SELECT id, name, actor_type, location_id FROM actors WHERE id = ?",
            (action.target_id,),
        ).fetchone()
        if target is None:
            return ActionResult(False, "TARGET_ACTOR_NOT_FOUND", "Такого персонажа нет.")
        if target["id"] == action.actor_id:
            return ActionResult(False, "INVALID_TARGET", "Нельзя передать предмет самому себе.")
        if target["location_id"] != location_id:
            return ActionResult(False, "TARGET_NOT_PRESENT", "Этого персонажа здесь нет.")

        conn.execute(
            "UPDATE entities SET owner_actor_id = ?, location_id = NULL WHERE id = ?",
            (target["id"], item["id"]),
        )
        relation_deltas: dict[str, dict[str, int]] = {}
        item_state = json.loads(item["state_json"])
        if target["actor_type"] == "npc" and item_state.get("edible") is True:
            relation_deltas[target["id"]] = self._apply_relation_delta(
                conn,
                source_actor_id=target["id"],
                target_actor_id=action.actor_id,
                now_text=now_text,
                deltas={"trust": 2, "affinity": 1},
            )

        evidence = {
            "item_id": item["id"],
            "target_id": target["id"],
            "relation_deltas": relation_deltas,
        }
        return ActionResult(
            True,
            "OK",
            f"Вы передаёте {item['name']} персонажу {target['name']}.",
            data=evidence,
        )

    def _buy(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        if action.item_id is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Не указано, что купить.")
        item = conn.execute(
            "SELECT id, name, location_id, owner_actor_id, state_json FROM entities WHERE id = ?",
            (action.item_id,),
        ).fetchone()
        if item is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такого товара нет.")
        if item["owner_actor_id"] is not None or item["location_id"] != location_id:
            return ActionResult(False, "TARGET_NOT_PRESENT", "Этого товара здесь нет.")

        state = json.loads(item["state_json"])
        price = state.get("price")
        seller_id = state.get("for_sale_by")
        if (
            isinstance(price, bool)
            or not isinstance(price, int)
            or price <= 0
            or not isinstance(seller_id, str)
            or not seller_id
        ):
            return ActionResult(False, "ITEM_NOT_FOR_SALE", "Этот предмет не продаётся.")
        if action.target_id != seller_id:
            return ActionResult(False, "WRONG_SELLER", "Этот товар продаёт другой персонаж.")

        seller = conn.execute(
            """
            SELECT a.id, a.location_id, n.coins
            FROM actors a
            JOIN npcs n ON n.actor_id = a.id
            WHERE a.id = ?
            """,
            (seller_id,),
        ).fetchone()
        if seller is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Продавец не найден.")
        if seller["location_id"] != location_id:
            return ActionResult(False, "SELLER_NOT_PRESENT", "Продавца сейчас здесь нет.")

        buyer = conn.execute(
            "SELECT coins FROM players WHERE actor_id = ?",
            (action.actor_id,),
        ).fetchone()
        buyer_before = int(buyer["coins"])
        seller_before = int(seller["coins"])
        if buyer_before < price:
            return ActionResult(False, "INSUFFICIENT_FUNDS", "Недостаточно монет.")

        buyer_after = buyer_before - price
        seller_after = seller_before + price
        conn.execute(
            "UPDATE players SET coins = ? WHERE actor_id = ?",
            (buyer_after, action.actor_id),
        )
        conn.execute(
            "UPDATE npcs SET coins = ? WHERE actor_id = ?",
            (seller_after, seller_id),
        )
        conn.execute(
            "UPDATE entities SET location_id = NULL, owner_actor_id = ? WHERE id = ?",
            (action.actor_id, action.item_id),
        )
        evidence = {
            "item_id": action.item_id,
            "seller_id": seller_id,
            "price": price,
            "buyer_coins_before": buyer_before,
            "buyer_coins_after": buyer_after,
            "seller_coins_before": seller_before,
            "seller_coins_after": seller_after,
        }
        return ActionResult(
            True,
            "OK",
            f"Вы покупаете {item['name']} за {price} монеты.",
            data=evidence,
        )

    def _use(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        if action.item_id is None:
            return ActionResult(False, "ITEM_NOT_OWNED", "Не указано, что использовать.")
        item = conn.execute(
            "SELECT id, name, owner_actor_id, state_json FROM entities WHERE id = ?",
            (action.item_id,),
        ).fetchone()
        if item is None or item["owner_actor_id"] != action.actor_id:
            return ActionResult(False, "ITEM_NOT_OWNED", "У вас нет этого предмета.")

        if action.target_id is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Не указана цель использования.")
        target = conn.execute(
            "SELECT id, name, location_id, state_json FROM entities WHERE id = ?",
            (action.target_id,),
        ).fetchone()
        if target is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такой цели нет.")
        if target["location_id"] != location_id:
            return ActionResult(False, "TARGET_NOT_PRESENT", "Этой цели здесь нет.")

        item_state = json.loads(item["state_json"])
        target_state = json.loads(target["state_json"])
        if item_state.get("fillable") is not True or target_state.get("water_source") is not True:
            return ActionResult(False, "UNSUPPORTED_USE", "Так использовать этот предмет пока нельзя.")
        filled_before = item_state.get("filled_with")
        if filled_before is not None:
            return ActionResult(False, "ITEM_ALREADY_FILLED", "Ёмкость уже наполнена.")

        item_state["filled_with"] = "water"
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE id = ?",
            (json.dumps(item_state, ensure_ascii=False, sort_keys=True), action.item_id),
        )
        evidence = {
            "item_id": action.item_id,
            "target_id": action.target_id,
            "filled_before": filled_before,
            "filled_after": "water",
        }
        return ActionResult(
            True,
            "OK",
            f"Вы наполняете {item['name']} водой из {target['name']}.",
            data=evidence,
        )

    def _drop(self, conn, action: CanonicalAction, location_id: str) -> ActionResult:
        if action.target_id is None:
            return ActionResult(False, "ITEM_NOT_OWNED", "Не указано, что положить.")
        entity = conn.execute(
            "SELECT id, name, owner_actor_id FROM entities WHERE id = ?",
            (action.target_id,),
        ).fetchone()
        if entity is None:
            return ActionResult(False, "TARGET_NOT_FOUND", "Такого предмета нет.")
        if entity["owner_actor_id"] != action.actor_id:
            return ActionResult(False, "ITEM_NOT_OWNED", "У вас нет этого предмета.")
        conn.execute(
            "UPDATE entities SET owner_actor_id = NULL, location_id = ? WHERE id = ?",
            (location_id, action.target_id),
        )
        return ActionResult(True, "OK", f"Вы кладёте {entity['name']}.", data={"entity_id": action.target_id})

    @staticmethod
    def _store_interaction(conn, external_id: str | None, actor_id: str, result: ActionResult, now_text: str) -> None:
        if external_id is None:
            return
        payload = json.dumps(
            {
                "success": result.success,
                "code": result.code,
                "summary": result.summary,
                "event_id": result.event_id,
                "data": result.data,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        conn.execute(
            """
            INSERT INTO processed_interactions(
                external_id, world_id, actor_id, action_event_id, result_json, processed_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (external_id, WORLD_ID, actor_id, result.event_id, payload, now_text),
        )

    @staticmethod
    def _append_event(conn, action: CanonicalAction, result: ActionResult, external_id: str | None, now_text: str, location_id: str | None) -> int:
        cursor = conn.execute(
            """
            INSERT INTO action_events(
                world_id, external_id, occurred_at, actor_id, action_type,
                target_id, location_id, success, result_code, summary, evidence_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                WORLD_ID,
                external_id,
                now_text,
                action.actor_id,
                action.action_type.value,
                action.target_id,
                location_id,
                int(result.success),
                result.code,
                result.summary,
                json.dumps(result.data, ensure_ascii=False, sort_keys=True),
            ),
        )
        return int(cursor.lastrowid)

    def observe(self, player_id: str) -> WorldView:
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self.synchronizer.catch_up(conn, WORLD_ID, self.clock.now())
                player = conn.execute(
                    """
                    SELECT a.id, a.location_id, l.name AS location_name, l.description, p.coins
                    FROM actors a
                    JOIN players p ON p.actor_id = a.id
                    JOIN locations l ON l.id = a.location_id
                    WHERE a.id = ?
                    """,
                    (player_id,),
                ).fetchone()
                if player is None:
                    raise KeyError(f"unknown player: {player_id}")

                actor_rows = conn.execute(
                    """
                    SELECT a.id, a.name, a.actor_type, n.current_activity
                    FROM actors a
                    LEFT JOIN npcs n ON n.actor_id = a.id
                    WHERE a.location_id = ? AND a.id != ?
                    ORDER BY a.actor_type, a.name, a.id
                    """,
                    (player["location_id"], player_id),
                ).fetchall()
                entity_rows = conn.execute(
                    """
                    SELECT id, name, entity_type, portable, state_json
                    FROM entities
                    WHERE location_id = ?
                    ORDER BY id
                    """,
                    (player["location_id"],),
                ).fetchall()
                inventory_rows = conn.execute(
                    """
                    SELECT id, name, entity_type, portable, state_json
                    FROM entities
                    WHERE owner_actor_id = ?
                    ORDER BY id
                    """,
                    (player_id,),
                ).fetchall()
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return WorldView(
            player_id=player_id,
            coins=int(player["coins"]),
            location_id=player["location_id"],
            location_name=player["location_name"],
            location_description=player["description"],
            actors=tuple(
                VisibleActor(
                    id=row["id"],
                    name=row["name"],
                    actor_type=row["actor_type"],
                    activity=row["current_activity"],
                )
                for row in actor_rows
            ),
            entities=tuple(
                VisibleEntity(
                    id=row["id"],
                    name=row["name"],
                    entity_type=row["entity_type"],
                    portable=bool(row["portable"]),
                    state=json.loads(row["state_json"]),
                )
                for row in entity_rows
            ),
            inventory=tuple(
                VisibleEntity(
                    id=row["id"],
                    name=row["name"],
                    entity_type=row["entity_type"],
                    portable=bool(row["portable"]),
                    state=json.loads(row["state_json"]),
                )
                for row in inventory_rows
            ),
        )
