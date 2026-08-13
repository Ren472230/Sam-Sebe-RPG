from __future__ import annotations

import json
import sqlite3
from typing import Any


class SocialService:
    GIFT_RULES: dict[str, dict[str, tuple[int, int]]] = {
        "mira_craftswoman": {
            "flat_stone": (1, 2),
            "round_stone": (1, 2),
            "useful_wood": (1, 0),
        },
        "kaspar_forager": {
            "pinecone": (1, 1),
        },
    }

    def get_trust(
        self, conn: sqlite3.Connection, source_id: str, target_id: str
    ) -> float:
        row = conn.execute(
            """
            SELECT value
            FROM relations
            WHERE source_id = ? AND target_id = ? AND relation_type = 'trust'
            """,
            (source_id, target_id),
        ).fetchone()
        return float(row["value"]) if row else 0.0

    def change_trust(
        self, conn: sqlite3.Connection, source_id: str, target_id: str, delta: float
    ) -> float:
        new_value = self.get_trust(conn, source_id, target_id) + delta
        conn.execute(
            """
            INSERT INTO relations(source_id, target_id, relation_type, value)
            VALUES (?, ?, 'trust', ?)
            ON CONFLICT(source_id, target_id, relation_type)
            DO UPDATE SET value = excluded.value
            """,
            (source_id, target_id, new_value),
        )
        return new_value

    def talk_summary(
        self,
        npc_id: str,
        trust: float,
        topic: str | None = None,
        *,
        state: dict[str, Any] | None = None,
    ) -> str:
        state = state or {}
        if npc_id == "mira_craftswoman":
            if bool(state.get("requested_wood", False)) and int(state.get("wood_stock", 0)) == 0:
                return (
                    "Мира отодвигает незаконченные заготовки: древесина кончилась, "
                    "и теперь она ждёт материал, чтобы продолжить работу."
                )
            if int(state.get("work_cycles", 0)) > 0 and int(state.get("wood_stock", 0)) > 0:
                return "Мира снова работает: запас древесины пока позволяет продолжать."
            return (
                "Мира перебирает заготовки: хорошие камни и необычные материалы "
                "здесь всегда находят применение."
            )
        if npc_id == "kaspar_forager":
            return (
                "Каспар поглядывает в сторону реки: он замечает то, "
                "что другие проходят мимо."
            )
        if npc_id == "oren_innkeeper":
            if topic == "lodging":
                return (
                    "Орен говорит, что место на ночь стоит 3 монеты; "
                    "знакомому местных он тоже может пойти навстречу."
                )
            return "Орен следит за площадью и спокойно оценивает нового человека."
        return "Разговор получается коротким."

    def apply_gift(
        self,
        conn: sqlite3.Connection,
        player_id: str,
        npc_id: str,
        item_id: str,
        item_tags: list[str],
    ) -> dict[str, Any]:
        npc_row = conn.execute(
            "SELECT state_json FROM entities WHERE entity_id = ?", (npc_id,)
        ).fetchone()
        state = json.loads(npc_row["state_json"]) if npc_row else {}
        received = set(state.get("received_contributions", []))

        accepted_key: str | None = None
        trust_delta = 0
        coins_delta = 0
        rules = self.GIFT_RULES.get(npc_id, {})
        for tag in item_tags:
            if tag in rules:
                accepted_key = tag
                if tag not in received:
                    trust_delta, coins_delta = rules[tag]
                    received.add(tag)
                break

        wood_stock_delta = 0
        request_cleared = False
        if npc_id == "mira_craftswoman" and "useful_wood" in item_tags:
            state["wood_stock"] = int(state.get("wood_stock", 0)) + 1
            request_cleared = bool(state.get("requested_wood", False))
            state["requested_wood"] = False
            wood_stock_delta = 1

        if trust_delta:
            self.change_trust(conn, npc_id, player_id, trust_delta)
        if coins_delta:
            conn.execute(
                "UPDATE player_resources SET coins = coins + ? WHERE player_id = ?",
                (coins_delta, player_id),
            )
        if accepted_key is not None or wood_stock_delta:
            state["received_contributions"] = sorted(received)
            conn.execute(
                "UPDATE entities SET state_json = ? WHERE entity_id = ?",
                (json.dumps(state, ensure_ascii=False), npc_id),
            )

        return {
            "trust_delta": trust_delta,
            "coins_delta": coins_delta,
            "accepted_key": accepted_key,
            "wood_stock_delta": wood_stock_delta,
            "request_cleared": request_cleared,
        }

    def pay_lodging(self, conn: sqlite3.Connection, player_id: str) -> dict[str, Any]:
        resources = conn.execute(
            "SELECT coins, lodging_secured FROM player_resources WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        if resources is None:
            return {"secured": False, "route": "coins", "reason": "missing_player"}
        if bool(resources["lodging_secured"]):
            return {"secured": True, "route": "already", "coins_spent": 0}
        if int(resources["coins"]) < 3:
            return {
                "secured": False,
                "route": "coins",
                "reason": "not_enough_coins",
                "coins_spent": 0,
            }
        conn.execute(
            """
            UPDATE player_resources
            SET coins = coins - 3, lodging_secured = 1
            WHERE player_id = ?
            """,
            (player_id,),
        )
        return {"secured": True, "route": "coins", "coins_spent": 3}

    def request_lodging(
        self, conn: sqlite3.Connection, player_id: str
    ) -> dict[str, Any]:
        resources = conn.execute(
            "SELECT lodging_secured FROM player_resources WHERE player_id = ?",
            (player_id,),
        ).fetchone()
        if resources is not None and bool(resources["lodging_secured"]):
            return {"secured": True, "route": "already"}

        for npc_id in ("mira_craftswoman", "kaspar_forager"):
            if self.get_trust(conn, npc_id, player_id) >= 3:
                conn.execute(
                    "UPDATE player_resources SET lodging_secured = 1 WHERE player_id = ?",
                    (player_id,),
                )
                return {"secured": True, "route": "trust", "trusted_by": npc_id}
        return {"secured": False, "route": "trust", "reason": "insufficient_trust"}

    def feed_animal(
        self,
        conn: sqlite3.Connection,
        player_id: str,
        animal_id: str,
        item_id: str,
    ) -> dict[str, Any]:
        row = conn.execute(
            "SELECT state_json FROM entities WHERE entity_id = ?", (animal_id,)
        ).fetchone()
        state = json.loads(row["state_json"]) if row else {}
        state["trust"] = int(state.get("trust", 0)) + 1
        conn.execute(
            "UPDATE entities SET state_json = ? WHERE entity_id = ?",
            (json.dumps(state, ensure_ascii=False), animal_id),
        )
        return {"animal_trust": state["trust"]}
