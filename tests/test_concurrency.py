from datetime import datetime, timezone
from threading import Barrier, Thread

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def test_concurrent_take_of_same_item_has_exactly_one_winner(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    db = GameDatabase(tmp_path / "game.db")
    db.initialize()
    db.bootstrap_if_empty(now)
    setup = GameService(db, FakeClock(now))
    players = [
        setup.register_player("discord-a", "Ren"),
        setup.register_player("discord-b", "TestPlayer"),
    ]
    barrier = Barrier(2)
    results = []

    def worker(index):
        service = GameService(GameDatabase(db.path), FakeClock(now))
        barrier.wait()
        results.append(
            service.execute(
                CanonicalAction(
                    players[index], ActionType.TAKE, target_id="stone_flat_1"
                ),
                external_id=f"take-concurrent-{index}",
            )
        )

    threads = [Thread(target=worker, args=(0,)), Thread(target=worker, args=(1,))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(result.success for result in results) == 1
    assert sorted(result.code for result in results) == ["ALREADY_OWNED", "OK"]
    with db.connect() as conn:
        owner = conn.execute(
            "SELECT owner_actor_id FROM entities WHERE id = 'stone_flat_1'"
        ).fetchone()[0]
        assert owner in players
        assert conn.execute("SELECT COUNT(*) FROM action_events").fetchone()[0] == 2
