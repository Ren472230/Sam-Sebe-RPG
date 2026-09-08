from __future__ import annotations

from samseberpg.conversation_initiative import resolve_initiative
from samseberpg.conversation_state import NpcInnerState
from samseberpg.living_conversation import ConversationThreadState


def _state(
    *,
    pending_question: str | None = None,
    open_threads: tuple[str, ...] = (),
    last_seen_tick: int = 0,
) -> ConversationThreadState:
    return ConversationThreadState(
        last_topic=None,
        open_threads=open_threads,
        pending_question=pending_question,
        last_seen_tick=last_seen_tick,
        turn_count=1 if pending_question else 0,
    )


def _inner(concern: str = "current_activity") -> NpcInnerState:
    return NpcInnerState(
        mood="calm",
        secondary_mood="neutral",
        current_concern=concern,
        current_desire="continue_current_activity",
        availability="medium",
        stance="grounded",
    )


def test_pending_question_has_highest_priority() -> None:
    initiative = resolve_initiative(
        npc_id="npc_kaspar",
        thread_state=_state(
            pending_question="Ты вообще зачем сюда пришёл?",
            open_threads=("player_reason_for_arrival",),
        ),
        inner_state=_inner("useful_wood"),
        runtime_state={"goal": "collect_wood"},
        known_facts=(),
        own_events=("NPC_MOVED: Kaspar moved toward the river.",),
    )

    assert initiative is not None
    assert initiative.kind == "unfinished_thread"
    assert "зачем сюда пришёл" in initiative.cue


def test_mira_active_request_can_drive_initiative() -> None:
    initiative = resolve_initiative(
        npc_id="npc_mira",
        thread_state=_state(),
        inner_state=_inner("workshop_stopped"),
        runtime_state={"requested_wood": True, "wood_stock": 0},
        known_facts=(),
        own_events=(),
    )

    assert initiative is not None
    assert initiative.kind == "current_request"
    assert "древес" in initiative.cue.lower()


def test_oren_guest_request_can_drive_initiative() -> None:
    initiative = resolve_initiative(
        npc_id="npc_oren",
        thread_state=_state(),
        inner_state=_inner("guest_and_supplies"),
        runtime_state={"bread_requested": True, "bread_received": False},
        known_facts=(),
        own_events=(),
    )

    assert initiative is not None
    assert initiative.kind == "current_request"
    assert "гост" in initiative.cue.lower() or "хлеб" in initiative.cue.lower()


def test_new_grounded_event_can_be_an_observation() -> None:
    initiative = resolve_initiative(
        npc_id="npc_kaspar",
        thread_state=_state(last_seen_tick=2),
        inner_state=_inner(),
        runtime_state={},
        known_facts=(),
        own_events=("NPC_COLLECTED_RESOURCE: Kaspar collected useful wood.",),
    )

    assert initiative is not None
    assert initiative.kind == "recent_event"
    assert "wood" in initiative.cue.lower() or "древес" in initiative.cue.lower()


def test_no_grounded_reason_means_no_forced_initiative() -> None:
    initiative = resolve_initiative(
        npc_id="npc_oren",
        thread_state=_state(),
        inner_state=_inner(),
        runtime_state={},
        known_facts=(),
        own_events=(),
    )

    assert initiative is None
