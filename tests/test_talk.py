import json
from datetime import datetime, timezone

from samseberpg.clock import FakeClock
from samseberpg.db import GameDatabase
from samseberpg.domain import ActionType, CanonicalAction
from samseberpg.game import GameService


def make_game(tmp_path):
    now = datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc)
    path = tmp_path / "game.db"
    db = GameDatabase(path)
    db.initialize()
    db.bootstrap_if_empty(now)
    return path, db, GameService(db, FakeClock(now)), now


def test_talk_to_present_npc_increases_familiarity_and_records_evidence(tmp_path):
    _, db, game, _ = make_game(tmp_path)
    player = game.register_player("discord-talk", "Ren")
    action = CanonicalAction(player, ActionType.TALK, target_id="npc_mira", source_text="сказать npc_mira привет")
    result = game.execute(action, external_id="talk-mira-1")
    assert result.success is True
    assert result.data["target_id"] == "npc_mira"
    assert result.data["utterance"] == "сказать npc_mira привет"
    assert result.data["npc_activity"] == "работает за верстаком"
    assert result.data["relation_deltas"]["npc_mira"] == {"familiarity": 1}
    with db.connect() as conn:
        relation = conn.execute(
            "SELECT familiarity, trust, affinity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
            (player,),
        ).fetchone()
        evidence = json.loads(conn.execute("SELECT evidence_json FROM action_events WHERE id=?", (result.event_id,)).fetchone()[0])
    assert tuple(relation) == (1, 0, 0)
    assert evidence["relation_deltas"]["npc_mira"] == {"familiarity": 1}


def test_talk_to_absent_npc_or_player_fails_without_relation(tmp_path):
    _, db, game, _ = make_game(tmp_path)
    player = game.register_player("discord-talk-a", "Ren")
    other = game.register_player("discord-talk-b", "Other")
    absent = game.execute(CanonicalAction(player, ActionType.TALK, target_id="npc_oren", source_text="Орен?"))
    player_target = game.execute(CanonicalAction(player, ActionType.TALK, target_id=other, source_text="привет"))
    assert absent.code == "TARGET_NOT_PRESENT"
    assert player_target.code == "TARGET_NOT_NPC"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0


def test_talk_duplicate_interaction_changes_familiarity_once(tmp_path):
    _, db, game, _ = make_game(tmp_path)
    player = game.register_player("discord-talk-idem", "Ren")
    action = CanonicalAction(player, ActionType.TALK, target_id="npc_mira", source_text="привет, Мира")
    first = game.execute(action, external_id="same-talk")
    second = game.execute(action, external_id="same-talk")
    assert first.success and second.success and second.replayed
    with db.connect() as conn:
        familiarity = conn.execute(
            "SELECT familiarity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
            (player,),
        ).fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM action_events WHERE action_type='TALK'").fetchone()[0]
    assert familiarity == 1
    assert events == 1


def test_talk_familiarity_clamps_at_100_and_survives_restart(tmp_path):
    path, db, game, now = make_game(tmp_path)
    player = game.register_player("discord-talk-clamp", "Ren")
    with db.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO relations(source_actor_id,target_actor_id,familiarity,trust,affinity,fear,conflict,romance,updated_at) VALUES ('npc_mira', ?, 100, 0, 0, 0, 0, 0, ?)",
            (player, "2026-08-14T08:00:00+00:00"),
        )
        conn.commit()
    result = game.execute(CanonicalAction(player, ActionType.TALK, target_id="npc_mira", source_text="ещё разговор"))
    assert result.data["relation_deltas"]["npc_mira"] == {"familiarity": 0}
    reopened = GameDatabase(path)
    reopened.initialize()
    GameService(reopened, FakeClock(now)).observe(player)
    with reopened.connect() as conn:
        assert conn.execute(
            "SELECT familiarity FROM relations WHERE source_actor_id='npc_mira' AND target_actor_id=?",
            (player,),
        ).fetchone()[0] == 100
