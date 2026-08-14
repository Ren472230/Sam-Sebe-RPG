from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier, Thread

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def test_concurrent_take_of_one_item_has_exactly_one_winner(tmp_path: Path) -> None:
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    clock = FakeClock(datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc))
    game = GameService(db, clock)
    player_a = game.register_player("discord-a", "Ari")
    player_b = game.register_player("discord-b", "Bela")
    barrier = Barrier(3)
    results = []
    errors = []

    def take(player_id: str, external_id: str) -> None:
        try:
            barrier.wait()
            results.append(
                game.execute(
                    CanonicalAction(actor_id=player_id, action_type=ActionType.TAKE, target_id="stone_flat_1"),
                    external_id=external_id,
                )
            )
        except BaseException as exc:
            errors.append(exc)

    threads = [
        Thread(target=take, args=(player_a, "concurrent-a")),
        Thread(target=take, args=(player_b, "concurrent-b")),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)
    assert errors == []
    assert len(results) == 2
    assert sum(result.success for result in results) == 1
    assert sorted(result.code for result in results) == ["ALREADY_OWNED", "OK"]
    with db.connect() as conn:
        owner = conn.execute("SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'").fetchone()[0]
        events = conn.execute(
            "SELECT external_id, success, result_code FROM action_events "
            "WHERE external_id IN ('concurrent-a', 'concurrent-b') ORDER BY external_id"
        ).fetchall()
    assert owner in {player_a, player_b}
    assert len(events) == 2
    assert sum(row[1] for row in events) == 1
