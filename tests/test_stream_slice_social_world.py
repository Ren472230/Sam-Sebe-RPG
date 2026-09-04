from __future__ import annotations

from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.social_world import SocialWorldService


EVENING = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)
FACT_KEY = "wayfarer_eastern_road_delay:v1"
FACT_TEXT = (
    "Heavy rain washed out part of the eastern road, so the next merchant "
    "caravan will be delayed."
)


def test_wayfarer_arrival_teaches_only_talen_and_oren_with_provenance(tmp_path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    game = GameService(
        db,
        FakeClock(EVENING),
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    player_id = game.register_player("stream-social", "Stream Player")

    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": 10},
        ),
        external_id="stream-social-wait-10",
    )
    assert result.success is True

    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT id, knower_actor_id, fact_text, source_kind, source_actor_id, "
            "source_world_event_id, source_knowledge_id, confidence, shareable "
            "FROM npc_knowledge WHERE fact_key = ? ORDER BY knower_actor_id",
            (FACT_KEY,),
        ).fetchall()
        assert len(rows) == 2

        by_knower = {str(row[1]): row for row in rows}
        assert set(by_knower) == {"npc_oren", "npc_wayfarer_1"}

        talen = by_knower["npc_wayfarer_1"]
        assert str(talen[2]) == FACT_TEXT
        assert str(talen[3]) == "direct_event"
        assert str(talen[4]) == "npc_wayfarer_1"
        assert talen[5] is not None
        assert talen[6] is None
        assert int(talen[7]) == 100
        assert int(talen[8]) == 1

        oren = by_knower["npc_oren"]
        assert str(oren[2]) == FACT_TEXT
        assert str(oren[3]) == "npc_report"
        assert str(oren[4]) == "npc_wayfarer_1"
        assert oren[5] is not None
        assert int(oren[6]) == int(talen[0])
        assert int(oren[7]) == 95
        assert int(oren[8]) == 1

        arrival_id = conn.execute(
            "SELECT id FROM world_events WHERE event_type = 'WAYFARER_ARRIVED'"
        ).fetchone()[0]
        assert int(talen[5]) == int(arrival_id)
        assert int(oren[5]) == int(arrival_id)

        assert conn.execute(
            "SELECT COUNT(*) FROM npc_knowledge "
            "WHERE fact_key = ? AND knower_actor_id IN ('npc_mira', 'npc_kaspar')",
            (FACT_KEY,),
        ).fetchone()[0] == 0
    finally:
        conn.close()
