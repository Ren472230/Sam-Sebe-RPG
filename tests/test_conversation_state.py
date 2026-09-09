from __future__ import annotations

import importlib
import importlib.util


def _module():
    spec = importlib.util.find_spec("samseberpg.conversation_state")
    assert spec is not None, "conversation_state module must exist"
    return importlib.import_module("samseberpg.conversation_state")


def _resolve(npc_id: str, *, runtime=None, activity="idle", relation=None, facts=()):
    module = _module()
    resolver = module.NpcConversationStateResolver()
    return resolver.resolve(
        npc_id=npc_id,
        runtime_state=runtime or {},
        activity=activity,
        relation=relation or {
            "familiarity": 0,
            "trust": 0,
            "affinity": 0,
            "fear": 0,
            "conflict": 0,
            "romance": 0,
        },
        known_facts=tuple(facts),
    )


def test_mira_blocked_workshop_changes_inner_state() -> None:
    state = _resolve(
        "npc_mira",
        runtime={"requested_wood": True, "wood_stock": 0},
        activity="working at the bench",
    )

    assert state.mood == "irritated"
    assert state.secondary_mood == "worried"
    assert state.current_concern == "workshop_stopped"
    assert state.current_desire == "obtain_useful_wood"
    assert state.availability == "low"
    assert state.stance == "work_first"


def test_mira_resolved_workshop_is_not_still_irritated() -> None:
    state = _resolve(
        "npc_mira",
        runtime={"requested_wood": False, "wood_stock": 2},
        activity="working at the bench",
    )

    assert state.mood == "focused"
    assert state.current_concern == "keep_workshop_running"
    assert state.current_desire == "continue_work"
    assert state.stance == "work_first"


def test_oren_reads_wayfarer_hospitality_as_supply_concern() -> None:
    state = _resolve(
        "npc_oren",
        runtime={"bread_requested": True, "bread_received": False},
        activity="running the inn",
        facts=(
            "source=npc_wayfarer_1 kind=npc_report: Heavy rain washed out part of the eastern road, so the next merchant caravan will be delayed. [confidence=95]",
        ),
    )

    assert state.mood == "concerned"
    assert state.secondary_mood == "hospitable"
    assert state.current_concern == "guest_and_supplies"
    assert state.current_desire == "care_for_guest"
    assert state.stance == "road_delay_threatens_supplies"


def test_kaspar_active_goal_preserves_independent_stance() -> None:
    state = _resolve(
        "npc_kaspar",
        runtime={"goal": "bring_useful_wood_to_mira", "carrying_wood": 0},
        activity="foraging along the river",
    )

    assert state.mood == "focused"
    assert state.secondary_mood == "skeptical"
    assert state.current_concern == "useful_wood"
    assert state.current_desire == "solve_it_himself"
    assert state.stance == "independence_over_promises"


def test_talen_known_road_fact_has_witness_stance() -> None:
    state = _resolve(
        "npc_wayfarer_1",
        runtime={"arrived": True},
        activity="resting after the road",
        facts=(
            "source=npc_wayfarer_1 kind=direct_event: Heavy rain washed out part of the eastern road, so the next merchant caravan will be delayed. [confidence=100]",
        ),
    )

    assert state.mood == "tired"
    assert state.secondary_mood == "wary"
    assert state.current_concern == "recover_from_road"
    assert state.current_desire == "rest_and_share_reliable_news"
    assert state.stance == "trust_what_i_saw"
