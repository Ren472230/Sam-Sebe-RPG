from __future__ import annotations

from pathlib import Path

from samseberpg.db import DEFAULT_WORLD_ID, GameDatabase
from samseberpg.living_conversation import LivingConversationStore


def _setup(tmp_path: Path):
    db = GameDatabase(tmp_path / "world.sqlite3")
    db.initialize()
    now = "2026-09-07T17:00:00.000Z"
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO actors (id, world_id, actor_type, name, location_id, created_at) "
            "VALUES ('player_lc', ?, 'player', 'Ничей', 'workshop_yard', ?)",
            (DEFAULT_WORLD_ID, now),
        )
        conn.execute(
            "INSERT INTO players (actor_id, discord_user_id, joined_at, coins) "
            "VALUES ('player_lc', 'living-conversation-test', ?, 10)",
            (now,),
        )
    return db, LivingConversationStore()


def test_player_claim_is_pair_scoped_and_persists(tmp_path: Path) -> None:
    db, store = _setup(tmp_path)
    with db.connect() as conn:
        store.ensure_schema(conn)
        store.add_memory(
            conn,
            world_id=DEFAULT_WORLD_ID,
            npc_actor_id="npc_mira",
            player_actor_id="player_lc",
            memory_type="player_claim",
            content="Игрок сказал, что раньше жил в столице.",
            source_kind="player_said",
            importance=65,
            created_tick=5,
        )

    reloaded = LivingConversationStore()
    with db.connect() as conn:
        reloaded.ensure_schema(conn)
        mira = reloaded.list_memories(conn, "npc_mira", "player_lc")
        kaspar = reloaded.list_memories(conn, "npc_kaspar", "player_lc")

    assert [item.content for item in mira] == ["Игрок сказал, что раньше жил в столице."]
    assert mira[0].memory_type == "player_claim"
    assert mira[0].source_kind == "player_said"
    assert kaspar == ()


def test_memory_validation_rejects_objective_or_unbounded_payloads(tmp_path: Path) -> None:
    db, store = _setup(tmp_path)
    with db.connect() as conn:
        store.ensure_schema(conn)
        for bad_type in ("world_fact", "secret_truth", ""):
            try:
                store.add_memory(
                    conn,
                    world_id=DEFAULT_WORLD_ID,
                    npc_actor_id="npc_mira",
                    player_actor_id="player_lc",
                    memory_type=bad_type,
                    content="test",
                    source_kind="player_said",
                    importance=50,
                    created_tick=1,
                )
            except ValueError:
                pass
            else:
                raise AssertionError(f"memory type should be rejected: {bad_type}")

        try:
            store.add_memory(
                conn,
                world_id=DEFAULT_WORLD_ID,
                npc_actor_id="npc_mira",
                player_actor_id="player_lc",
                memory_type="player_claim",
                content="x" * 241,
                source_kind="player_said",
                importance=50,
                created_tick=1,
            )
        except ValueError:
            pass
        else:
            raise AssertionError("oversized memory should be rejected")


def test_thread_survives_reopen_and_can_be_resolved(tmp_path: Path) -> None:
    db, store = _setup(tmp_path)
    with db.connect() as conn:
        store.ensure_schema(conn)
        store.note_turn(
            conn,
            npc_actor_id="npc_kaspar",
            player_actor_id="player_lc",
            last_topic="why_player_came_here",
            tick=6,
            pending_question="Ты вообще зачем сюда пришёл?",
        )
        store.open_thread(
            conn,
            npc_actor_id="npc_kaspar",
            player_actor_id="player_lc",
            thread="player_reason_for_arrival",
            tick=6,
        )

    with db.connect() as conn:
        store.ensure_schema(conn)
        state = store.get_thread_state(conn, "npc_kaspar", "player_lc")
        assert state.last_topic == "why_player_came_here"
        assert state.pending_question == "Ты вообще зачем сюда пришёл?"
        assert state.open_threads == ("player_reason_for_arrival",)
        assert state.last_seen_tick == 6
        assert state.turn_count == 1

        store.resolve_thread(
            conn,
            npc_actor_id="npc_kaspar",
            player_actor_id="player_lc",
            thread="player_reason_for_arrival",
            tick=9,
        )
        resolved = store.get_thread_state(conn, "npc_kaspar", "player_lc")

    assert resolved.open_threads == ()
    assert resolved.pending_question is None
    assert resolved.last_seen_tick == 9


def test_thread_state_is_isolated_between_npcs(tmp_path: Path) -> None:
    db, store = _setup(tmp_path)
    with db.connect() as conn:
        store.ensure_schema(conn)
        store.note_turn(
            conn,
            npc_actor_id="npc_mira",
            player_actor_id="player_lc",
            last_topic="wood",
            tick=4,
            pending_question="Так ты принесёшь древесину?",
        )
        mira = store.get_thread_state(conn, "npc_mira", "player_lc")
        oren = store.get_thread_state(conn, "npc_oren", "player_lc")

    assert mira.pending_question == "Так ты принесёшь древесину?"
    assert oren.pending_question is None
    assert oren.turn_count == 0


def test_duplicate_memory_is_reinforced_not_duplicated(tmp_path: Path) -> None:
    db, store = _setup(tmp_path)
    with db.connect() as conn:
        store.ensure_schema(conn)
        for _ in range(2):
            store.add_memory(
                conn,
                world_id=DEFAULT_WORLD_ID,
                npc_actor_id="npc_oren",
                player_actor_id="player_lc",
                memory_type="preference",
                content="Игрок сказал, что любит тишину.",
                source_kind="player_said",
                importance=40,
                created_tick=3,
            )
        memories = store.list_memories(conn, "npc_oren", "player_lc")

    assert len(memories) == 1
    assert memories[0].reinforcement_count == 1
