from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.dialogue import DialogueService
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService
from samseberpg.living_world import LivingWorldService
from samseberpg.quest import QuestService
from samseberpg.social_world import SocialWorldService


STREAM_NOW = datetime(2026, 8, 24, 17, 0, tzinfo=timezone.utc)
ROAD_FACT_KEY = "wayfarer_eastern_road_delay:v1"


def _services(path: Path):
    db = GameDatabase(path)
    db.initialize()
    clock = FakeClock(STREAM_NOW)
    game = GameService(
        db,
        clock,
        living_world=LivingWorldService(),
        social_world=SocialWorldService(),
    )
    dialogue = DialogueService(db, QuestService(db, clock), provider=None)
    return db, game, dialogue


def _move(game: GameService, player_id: str, destination: str) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.MOVE,
            destination_id=destination,
        )
    )
    assert result.success is True, (result.code, result.summary)


def _wait(game: GameService, player_id: str, ticks: int, key: str) -> None:
    result = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.WAIT,
            modifiers={"ticks": ticks},
        ),
        external_id=key,
    )
    assert result.success is True, (result.code, result.summary)


def test_stream_slice_full_causal_route_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "stream-acceptance.sqlite3"
    db, game, dialogue = _services(path)
    player_id = game.register_player("stream-acceptance", "Stream Player")

    # Mira's workshop becomes blocked and the player's promise is private to her.
    _wait(game, player_id, 5, "stream-to-mira-request")
    promise = dialogue.talk(
        player_id,
        "Я принесу тебе пригодную древесину.",
        npc_id="npc_mira",
    )
    assert promise.social_action is not None

    _move(game, player_id, "village_square")
    _move(game, player_id, "river_edge")
    before_contact = dialogue.talk(
        player_id,
        "Слышал что-нибудь обо мне и Мире?",
        npc_id="npc_kaspar",
    )
    assert "обещал помочь" not in before_contact.text.lower()

    # Kaspar independently completes the existing resource loop by tick 9.
    _wait(game, player_id, 4, "stream-to-kaspar-delivery")
    _move(game, player_id, "village_square")
    after_contact = dialogue.talk(
        player_id,
        "Что Мира тебе обо мне говорила?",
        npc_id="npc_kaspar",
    )
    assert "мира говорила" in after_contact.text.lower()
    assert "обещал помочь" in after_contact.text.lower()

    # The temporary visitor arrives at tick 10 and Oren receives his road news.
    _wait(game, player_id, 1, "stream-to-wayfarer-arrival")
    _move(game, player_id, "tavern_interior")

    talen = dialogue.talk(
        player_id,
        "Что случилось в дороге?",
        npc_id="npc_wayfarer_1",
    )
    assert "восточн" in talen.text.lower()
    assert "караван" in talen.text.lower()

    oren_news = dialogue.talk(
        player_id,
        "Что рассказал Тален?",
        npc_id="npc_oren",
    )
    assert "тален" in oren_news.text.lower()
    assert "восточн" in oren_news.text.lower()
    assert "караван" in oren_news.text.lower()

    oren_need = dialogue.talk(
        player_id,
        "Нужна помощь с гостем?",
        npc_id="npc_oren",
    )
    assert "хлеб" in oren_need.text.lower()

    # Reuse the already-existing physical loaf through canonical TAKE/GIVE.
    _move(game, player_id, "village_square")
    taken = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.TAKE,
            target_id="bread_loaf_1",
        )
    )
    assert taken.success is True
    _move(game, player_id, "tavern_interior")
    given = game.execute(
        CanonicalAction(
            actor_id=player_id,
            action_type=ActionType.GIVE,
            target_id="bread_loaf_1",
            recipient_id="npc_oren",
        )
    )
    assert given.success is True

    acknowledged = dialogue.talk(
        player_id,
        "Хлеб подошёл?",
        npc_id="npc_oren",
    )
    assert any(token in acknowledged.text.lower() for token in ("спасибо", "хлеб", "гост"))

    with db.connect() as conn:
        tick = int(conn.execute("SELECT tick FROM world_runtime WHERE world_id='village_1'").fetchone()[0])
        arrivals = int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events "
                "WHERE actor_id='npc_wayfarer_1' AND event_type='WAYFARER_ARRIVED'"
            ).fetchone()[0]
        )
        bread_requests = int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events "
                "WHERE actor_id='npc_oren' AND event_type='NPC_REQUESTED_RESOURCE' "
                "AND target_id='bread_loaf_1'"
            ).fetchone()[0]
        )
        knowers = [
            str(row[0])
            for row in conn.execute(
                "SELECT knower_actor_id FROM npc_knowledge WHERE fact_key=? ORDER BY knower_actor_id",
                (ROAD_FACT_KEY,),
            ).fetchall()
        ]
        kaspar_report = conn.execute(
            "SELECT source_kind, source_actor_id FROM npc_knowledge "
            "WHERE knower_actor_id='npc_kaspar' "
            "AND fact_key=?",
            (f"player_promised_mira_useful_wood:{player_id}",),
        ).fetchone()
        oren_runtime = conn.execute(
            "SELECT state_json FROM npc_runtime_state WHERE npc_actor_id='npc_oren'"
        ).fetchone()
        integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()

    assert tick == 10
    assert arrivals == 1
    assert bread_requests == 1
    assert knowers == ["npc_oren", "npc_wayfarer_1"]
    assert kaspar_report is not None
    assert tuple(kaspar_report) == ("npc_report", "npc_mira")
    assert oren_runtime is not None
    assert json.loads(str(oren_runtime[0])) == {
        "bread_received": True,
        "bread_requested": False,
    }
    assert integrity == "ok"
    assert fk_errors == []

    # Reopen the exact database and prove the causal state remains canonical.
    reopened_db, reopened_game, reopened_dialogue = _services(path)
    del reopened_game
    persisted = reopened_dialogue.talk(
        player_id,
        "Что рассказал Тален?",
        npc_id="npc_oren",
    )
    assert "тален" in persisted.text.lower()
    assert "караван" in persisted.text.lower()

    with reopened_db.connect() as conn:
        assert int(
            conn.execute(
                "SELECT COUNT(*) FROM world_events "
                "WHERE actor_id='npc_wayfarer_1' AND event_type='WAYFARER_ARRIVED'"
            ).fetchone()[0]
        ) == 1
        assert [
            str(row[0])
            for row in conn.execute(
                "SELECT knower_actor_id FROM npc_knowledge WHERE fact_key=? ORDER BY knower_actor_id",
                (ROAD_FACT_KEY,),
            ).fetchall()
        ] == ["npc_oren", "npc_wayfarer_1"]
