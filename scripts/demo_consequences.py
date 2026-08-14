from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def main() -> None:
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="sam-sebe-consequences-") as temp_dir:
        path = Path(temp_dir) / "game.db"
        db = GameDatabase(path)
        db.initialize()
        db.bootstrap_if_empty(now)
        game = GameService(db, FakeClock(now))

        ren = game.register_player("demo-ren", "Ren")
        observer = game.register_player("demo-observer", "Observer")

        assert game.execute(
            CanonicalAction(ren, ActionType.TAKE, target_id="stone_flat_1"),
            external_id="demo-take-stone",
        ).success
        assert game.execute(
            CanonicalAction(ren, ActionType.MOVE, destination_id="village_square"),
            external_id="demo-ren-square",
        ).success
        throw = game.execute(
            CanonicalAction(
                ren,
                ActionType.THROW,
                item_id="stone_flat_1",
                target_id="tavern_sign",
            ),
            external_id="demo-throw-sign",
        )
        assert throw.success
        print("[action] Ren бросил камень в вывеску таверны")

        assert game.execute(
            CanonicalAction(observer, ActionType.MOVE, destination_id="village_square"),
            external_id="demo-observer-square",
        ).success
        sign = next(
            entity
            for entity in game.observe(observer).entities
            if entity.id == "tavern_sign"
        )
        assert sign.state["condition"] == 80
        print("[shared consequence] Второй игрок видит состояние вывески: 80%")

        with db.connect() as conn:
            relation = conn.execute(
                """
                SELECT trust, affinity, conflict FROM relations
                WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?
                """,
                (ren,),
            ).fetchone()
            throw_evidence = json.loads(
                conn.execute(
                    "SELECT evidence_json FROM action_events WHERE id = ?",
                    (throw.event_id,),
                ).fetchone()[0]
            )
        assert tuple(relation) == (-3, 0, 4)
        assert throw_evidence["relation_deltas"]["npc_oren"]["trust"] == -3
        print("[witness] Орен видел поступок: trust -3, conflict +4")

        assert game.execute(
            CanonicalAction(ren, ActionType.TAKE, target_id="bread_1"),
            external_id="demo-take-bread",
        ).success
        gift = game.execute(
            CanonicalAction(
                ren,
                ActionType.GIVE,
                item_id="bread_1",
                target_id="npc_oren",
            ),
            external_id="demo-give-bread",
        )
        assert gift.success
        assert gift.data["relation_deltas"]["npc_oren"] == {"trust": 2, "affinity": 1}
        print("[social consequence] Хлеб Орену: trust +2, affinity +1")

        reopened = GameDatabase(path)
        reopened.initialize()
        restarted = GameService(reopened, FakeClock(now))
        persisted_sign = next(
            entity
            for entity in restarted.observe(observer).entities
            if entity.id == "tavern_sign"
        )
        assert persisted_sign.state["condition"] == 80
        with reopened.connect() as conn:
            persisted_relation = conn.execute(
                """
                SELECT trust, affinity, conflict FROM relations
                WHERE source_actor_id = 'npc_oren' AND target_actor_id = ?
                """,
                (ren,),
            ).fetchone()
        assert tuple(persisted_relation) == (-1, 1, 4)
        print("[persistence] После restart: вывеска 80%, Oren relation = (-1, +1, 4)")
        print("\nPersistent Consequences demo: PASS")


if __name__ == "__main__":
    main()
